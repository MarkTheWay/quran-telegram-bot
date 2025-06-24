#!/usr/bin/env python3
"""
GitHub Actions Quran Bot - Posts one verse per run
This version is specifically designed for GitHub Actions
"""

import pandas as pd
import requests
import json
import os
import logging
import base64
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GitHubActionsQuranBot:
    def __init__(self, bot_token: str, channel_id: str, csv_file_path: str):
        self.bot_token = bot_token
        self.channel_id = channel_id
        self.csv_file_path = csv_file_path
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.state_file = "bot_state.json"
        self.current_index = 0
        
        # Load dataset
        self.load_dataset()
        
        # Load state from GitHub repository
        self.load_state_from_github()
    
    def load_dataset(self):
        """Load the Quran dataset from CSV file"""
        try:
            self.verses_data = pd.read_csv(self.csv_file_path)
            logger.info(f"✅ Loaded {len(self.verses_data)} verses from dataset")
            
            # Verify required columns
            required_columns = ['ayah_ar', 'ayah_en', 'surah_name_en', 'ayah_no_surah', 'surah_no']
            missing_columns = [col for col in required_columns if col not in self.verses_data.columns]
            if missing_columns:
                raise ValueError(f"Missing required columns: {missing_columns}")
                
        except Exception as e:
            logger.error(f"❌ Error loading dataset: {e}")
            raise
    
    def load_state_from_github(self):
        """Load state from GitHub repository using API"""
        try:
            github_token = os.getenv('GITHUB_TOKEN')
            repo = os.getenv('GITHUB_REPOSITORY')
            
            if not github_token or not repo:
                logger.info("📝 GitHub credentials not available, starting from beginning")
                self.current_index = 0
                return
            
            # Try to get the state file from GitHub
            url = f"https://api.github.com/repos/{repo}/contents/{self.state_file}"
            headers = {
                'Authorization': f'token {github_token}',
                'Accept': 'application/vnd.github.v3+json'
            }
            
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                # File exists, decode and load
                content = response.json()
                file_content = base64.b64decode(content['content']).decode('utf-8')
                state = json.loads(file_content)
                self.current_index = state.get('current_index', 0)
                logger.info(f"📂 Loaded state from GitHub: current_index = {self.current_index}")
            else:
                # File doesn't exist, start from beginning
                logger.info("📝 No previous state found in GitHub, starting from beginning")
                self.current_index = 0
                
        except Exception as e:
            logger.error(f"⚠️ Error loading state from GitHub: {e}")
            self.current_index = 0
    
    def save_state_locally(self):
        """Save state to local file (will be committed by GitHub Actions)"""
        try:
            state = {
                'current_index': self.current_index,
                'last_run': datetime.now().isoformat(),
                'total_verses': len(self.verses_data) if self.verses_data is not None else 0
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
            
            logger.info(f"💾 Saved state locally: current_index = {self.current_index}")
            
        except Exception as e:
            logger.error(f"❌ Error saving state: {e}")
    
    def format_verse_message(self, verse_row) -> str:
        """Format a verse into a beautiful message for Telegram"""
        try:
            arabic_text = verse_row['ayah_ar']
            english_text = verse_row['ayah_en']
            surah_name = verse_row['surah_name_en']
            surah_no = int(verse_row['surah_no'])
            ayah_no = int(verse_row['ayah_no_surah'])
            
            # Calculate progress
            progress = ((self.current_index + 1) / len(self.verses_data)) * 100
            
            message = f"""🕌 *Verse of the Hour* 🕌

📖 *{surah_name}* ({surah_no}:{ayah_no})

🔸 *Arabic:*
{arabic_text}

🔸 *English:*
{english_text}

─────────────────
✨ May this verse bring peace and guidance to your heart ✨

📊 Progress: {self.current_index + 1}/{len(self.verses_data)} ({progress:.1f}%)

#Quran #Verse #Islam #Guidance #AutomatedByGitHub"""
            
            return message
            
        except Exception as e:
            logger.error(f"❌ Error formatting message: {e}")
            return None
    
    def send_message(self, message: str) -> bool:
        """Send a message to the Telegram channel"""
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                'chat_id': self.channel_id,
                'text': message,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    logger.info("✅ Message sent successfully to Telegram")
                    return True
                else:
                    error_desc = result.get('description', 'Unknown error')
                    logger.error(f"❌ Telegram API error: {error_desc}")
                    return False
            else:
                logger.error(f"❌ HTTP error: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error sending message: {e}")
            return False
    
    def test_telegram_connection(self) -> bool:
        """Test if the bot can connect to Telegram"""
        try:
            url = f"{self.base_url}/getMe"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    bot_info = result['result']
                    logger.info(f"🤖 Bot connected: @{bot_info.get('username', 'unknown')}")
                    return True
            
            logger.error("❌ Failed to connect to Telegram bot")
            return False
            
        except Exception as e:
            logger.error(f"❌ Error testing Telegram connection: {e}")
            return False
    
    def post_single_verse(self) -> bool:
        """Post a single verse and update state"""
        try:
            if self.verses_data is None or len(self.verses_data) == 0:
                logger.error("❌ No verses data available")
                return False
            
            # Test Telegram connection first
            if not self.test_telegram_connection():
                return False
            
            # Get the current verse
            if self.current_index >= len(self.verses_data):
                self.current_index = 0  # Reset to beginning
                logger.info("🔄 Reached end of dataset, restarting from beginning")
            
            current_verse = self.verses_data.iloc[self.current_index]
            
            # Format the message
            message = self.format_verse_message(current_verse)
            if not message:
                logger.error("❌ Failed to format message")
                return False
            
            # Send the message
            if self.send_message(message):
                surah_name = current_verse['surah_name_en']
                surah_no = current_verse['surah_no']
                ayah_no = current_verse['ayah_no_surah']
                
                logger.info(f"📤 Posted verse {self.current_index + 1}/{len(self.verses_data)}: "
                           f"{surah_name} {surah_no}:{ayah_no}")
                
                # Move to next verse and save state
                self.current_index += 1
                self.save_state_locally()
                return True
            else:
                logger.error("❌ Failed to send message to Telegram")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error posting verse: {e}")
            return False

def main():
    """Main function - posts one verse then exits"""
    
    logger.info("🚀 Starting GitHub Actions Quran Bot...")
    
    # Get configuration from environment variables
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    CHANNEL_ID = os.getenv("CHANNEL_ID")
    CSV_FILE_PATH = "quran_dataset.csv"
    
    # Validate configuration
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN environment variable not set")
        logger.info("💡 Add your bot token to GitHub repository secrets")
        return False
    
    if not CHANNEL_ID:
        logger.error("❌ CHANNEL_ID environment variable not set")
        logger.info("💡 Add your channel ID to GitHub repository secrets")
        return False
    
    if not os.path.exists(CSV_FILE_PATH):
        logger.error(f"❌ CSV file not found: {CSV_FILE_PATH}")
        logger.info("💡 Make sure to upload your quran_dataset.csv file to the repository")
        return False
    
    # Create and run the bot
    try:
        bot = GitHubActionsQuranBot(BOT_TOKEN, CHANNEL_ID, CSV_FILE_PATH)
        success = bot.post_single_verse()
        
        if success:
            logger.info("✅ Verse posted successfully! 🎉")
            return True
        else:
            logger.error("❌ Failed to post verse")
            return False
            
    except Exception as e:
        logger.error(f"💥 Bot crashed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)