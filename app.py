import streamlit as st
import pandas as pd
import requests
import json
from datetime import datetime, timedelta
import google.generativeai as genai
from typing import List, Dict, Any
import time
import re
import os
from urllib.parse import urlparse
import base64
from io import BytesIO
from PIL import Image
from dotenv import load_dotenv
import yaml
from pathlib import Path

# Load environment variables
load_dotenv()

# Configure page
st.set_page_config(
    page_title="Instagram Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern UI
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 800;
        color: #1f2937;
        text-align: center;
        margin-bottom: 2rem;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 1rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        border: 1px solid #e5e7eb;
        margin-bottom: 1rem;
    }
    
    .post-card {
        background: white;
        border-radius: 1rem;
        overflow: hidden;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        border: 1px solid #e5e7eb;
        transition: transform 0.2s;
        margin-bottom: 1.5rem;
    }
    
    .post-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 15px -3px rgba(0, 0, 0, 0.1);
    }
    
    .post-thumbnail {
        width: 100%;
        height: 200px;
        object-fit: cover;
    }
    
    .post-content {
        padding: 1rem;
    }
    
    .creator-name {
        font-weight: 600;
        color: #1f2937;
        font-size: 0.9rem;
        margin-bottom: 0.5rem;
    }
    
    .post-stats {
        display: flex;
        justify-content: space-between;
        font-size: 0.8rem;
        color: #6b7280;
        margin-top: 0.5rem;
    }
    
    .filter-container {
        background: #f9fafb;
        padding: 1.5rem;
        border-radius: 1rem;
        border: 1px solid #e5e7eb;
        margin-bottom: 2rem;
    }
    
    .hashtag-tag {
        display: inline-block;
        background: #3b82f6;
        color: white;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.8rem;
        margin: 0.25rem;
    }
    
    .bookmark-btn {
        background: #ef4444;
        color: white;
        border: none;
        padding: 0.5rem 1rem;
        border-radius: 0.5rem;
        cursor: pointer;
        font-size: 0.8rem;
    }
    
    .bookmark-btn:hover {
        background: #dc2626;
    }
    
    .loading-spinner {
        display: flex;
        justify-content: center;
        align-items: center;
        height: 100px;
    }
</style>
""", unsafe_allow_html=True)

class SecretsManager:
    """Handles all API keys and secrets management"""
    
    def __init__(self):
        self.secrets_file = Path(".streamlit/secrets.toml")
        self.env_file = Path(".env")
        self.config_file = Path("config.yaml")
        self.api_keys = {}
        self.load_secrets()
    
    def load_secrets(self):
        """Load secrets from multiple sources in priority order"""
        # Priority 1: Streamlit secrets (for cloud deployment)
        try:
            self.api_keys.update({
                'apify_token': st.secrets.get("APIFY_TOKEN", ""),
                'gemini_api_key': st.secrets.get("GEMINI_API_KEY", ""),
                'instagram_session_id': st.secrets.get("INSTAGRAM_SESSION_ID", ""),
                'proxy_url': st.secrets.get("PROXY_URL", ""),
                'openai_api_key': st.secrets.get("OPENAI_API_KEY", "")
            })
        except:
            pass
        
        # Priority 2: Environment variables
        env_keys = {
            'apify_token': os.getenv("APIFY_TOKEN", ""),
            'gemini_api_key': os.getenv("GEMINI_API_KEY", ""),
            'instagram_session_id': os.getenv("INSTAGRAM_SESSION_ID", ""),
            'proxy_url': os.getenv("PROXY_URL", ""),
            'openai_api_key': os.getenv("OPENAI_API_KEY", "")
        }
        
        # Update with non-empty env vars
        for key, value in env_keys.items():
            if value and not self.api_keys.get(key):
                self.api_keys[key] = value
        
        # Priority 3: Local secrets file
        if self.secrets_file.exists():
            try:
                import tomli
                with open(self.secrets_file, 'rb') as f:
                    secrets_data = tomli.load(f)
                    for key in ['APIFY_TOKEN', 'GEMINI_API_KEY', 'INSTAGRAM_SESSION_ID', 'PROXY_URL', 'OPENAI_API_KEY']:
                        if key in secrets_data and not self.api_keys.get(key.lower()):
                            self.api_keys[key.lower()] = secrets_data[key]
            except:
                pass
        
        # Priority 4: Config file
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    config_data = yaml.safe_load(f)
                    api_section = config_data.get('api_keys', {})
                    for key, value in api_section.items():
                        if value and not self.api_keys.get(key):
                            self.api_keys[key] = value
            except:
                pass
    
    def save_secrets_to_file(self, secrets_dict: Dict[str, str], file_type: str = "toml"):
        """Save secrets to local file"""
        if file_type == "toml":
            self.secrets_file.parent.mkdir(exist_ok=True)
            toml_content = ""
            for key, value in secrets_dict.items():
                if value:
                    toml_content += f'{key.upper()} = "{value}"\n'
            
            with open(self.secrets_file, 'w') as f:
                f.write(toml_content)
                
        elif file_type == "env":
            env_content = ""
            for key, value in secrets_dict.items():
                if value:
                    env_content += f'{key.upper()}={value}\n'
            
            with open(self.env_file, 'w') as f:
                f.write(env_content)
        
        elif file_type == "yaml":
            config_data = {
                'api_keys': secrets_dict,
                'app_settings': {
                    'debug_mode': False,
                    'cache_enabled': True,
                    'max_posts_per_request': 100
                }
            }
            
            with open(self.config_file, 'w') as f:
                yaml.dump(config_data, f, default_flow_style=False)
    
    def get_secret(self, key: str) -> str:
        """Get a secret value"""
        return self.api_keys.get(key.lower(), "")
    
    def has_required_keys(self) -> bool:
        """Check if all required API keys are available"""
        required_keys = ['apify_token', 'gemini_api_key']
        return all(self.get_secret(key) for key in required_keys)
    
    def get_missing_keys(self) -> List[str]:
        """Get list of missing required API keys"""
        required_keys = ['apify_token', 'gemini_api_key']
        return [key for key in required_keys if not self.get_secret(key)]
    
    def show_setup_wizard(self):
        """Display setup wizard for API keys"""
        st.error("🔑 API Keys Required")
        st.markdown("""
        This app requires API keys to function. Please provide them below:
        """)
        
        with st.expander("🛠️ API Keys Setup", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### Required Keys")
                apify_token = st.text_input(
                    "Apify Token",
                    value=self.get_secret('apify_token'),
                    type="password",
                    help="Get from: https://console.apify.com/account/integrations"
                )
                
                gemini_key = st.text_input(
                    "Google Gemini API Key",
                    value=self.get_secret('gemini_api_key'),
                    type="password",
                    help="Get from: https://makersuite.google.com/app/apikey"
                )
            
            with col2:
                st.markdown("### Optional Keys")
                instagram_session = st.text_input(
                    "Instagram Session ID",
                    value=self.get_secret('instagram_session_id'),
                    type="password",
                    help="For enhanced scraping (optional)"
                )
                
                proxy_url = st.text_input(
                    "Proxy URL",
                    value=self.get_secret('proxy_url'),
                    help="For avoiding rate limits (optional)"
                )
                
                openai_key = st.text_input(
                    "OpenAI API Key",
                    value=self.get_secret('openai_api_key'),
                    type="password",
                    help="Alternative to Gemini (optional)"
                )
            
            st.markdown("### Save Configuration")
            save_format = st.selectbox(
                "Save format",
                ["TOML (.streamlit/secrets.toml)", "Environment (.env)", "YAML (config.yaml)"],
                help="Choose how to save your API keys"
            )
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("💾 Save Keys", type="primary"):
                    secrets_dict = {
                        'apify_token': apify_token,
                        'gemini_api_key': gemini_key,
                        'instagram_session_id': instagram_session,
                        'proxy_url': proxy_url,
                        'openai_api_key': openai_key
                    }
                    
                    format_map = {
                        "TOML (.streamlit/secrets.toml)": "toml",
                        "Environment (.env)": "env", 
                        "YAML (config.yaml)": "yaml"
                    }
                    
                    self.save_secrets_to_file(secrets_dict, format_map[save_format])
                    self.load_secrets()  # Reload secrets
                    st.success(f"✅ Keys saved to {save_format}")
                    st.experimental_rerun()
            
            with col2:
                if st.button("🔄 Reload Keys"):
                    self.load_secrets()
                    st.success("✅ Keys reloaded")
                    st.experimental_rerun()
            
            with col3:
                if st.button("🧪 Test Keys"):
                    self.test_api_keys()
        
        # Show instructions
        with st.expander("📖 How to Get API Keys"):
            st.markdown("""
            ### 🔧 Apify Token
            1. Sign up at [apify.com](https://apify.com) (free tier available)
            2. Go to **Console → Account → Integrations**
            3. Create a new API token
            4. Copy the token
            
            ### 🤖 Google Gemini API Key  
            1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
            2. Click **Create API Key**
            3. Copy the generated key
            
            ### 📱 Instagram Session ID (Optional)
            1. Open Instagram in browser
            2. Login to your account
            3. Open Developer Tools (F12)
            4. Go to Application → Cookies
            5. Find 'sessionid' cookie value
            
            ### 🌐 Proxy URL (Optional)
            - Use services like ProxyMesh, Bright Data, or Smartproxy
            - Format: `http://username:password@proxy-server:port`
            
            ### 🔑 OpenAI API Key (Alternative to Gemini)
            1. Visit [OpenAI Platform](https://platform.openai.com/api-keys)
            2. Create new secret key
            3. Copy the key
            """)
        
        return False  # Keys not ready
    
    def test_api_keys(self):
        """Test if API keys are working"""
        results = {}
        
        # Test Apify
        if self.get_secret('apify_token'):
            try:
                response = requests.get(
                    "https://api.apify.com/v2/users/me",
                    headers={'Authorization': f'Bearer {self.get_secret("apify_token")}'}
                )
                results['Apify'] = "✅ Valid" if response.status_code == 200 else "❌ Invalid"
            except:
                results['Apify'] = "❌ Connection Error"
        else:
            results['Apify'] = "⚠️ Not Set"
        
        # Test Gemini
        if self.get_secret('gemini_api_key'):
            try:
                genai.configure(api_key=self.get_secret('gemini_api_key'))
                model = genai.GenerativeModel('gemini-pro')
                response = model.generate_content("Hello")
                results['Gemini'] = "✅ Valid"
            except:
                results['Gemini'] = "❌ Invalid"
        else:
            results['Gemini'] = "⚠️ Not Set"
        
        # Display results
        st.markdown("### 🧪 API Key Test Results")
        for service, status in results.items():
            st.markdown(f"**{service}**: {status}")

class InstagramAnalytics:
    def __init__(self):
        self.secrets_manager = SecretsManager()
        
        # Get API keys from secrets manager
        self.apify_token = self.secrets_manager.get_secret('apify_token')
        self.gemini_api_key = self.secrets_manager.get_secret('gemini_api_key')
        self.instagram_session_id = self.secrets_manager.get_secret('instagram_session_id')
        self.proxy_url = self.secrets_manager.get_secret('proxy_url')
        self.openai_api_key = self.secrets_manager.get_secret('openai_api_key')
        
        # Configure Gemini AI
        if self.gemini_api_key:
            try:
                genai.configure(api_key=self.gemini_api_key)
                self.model = genai.GenerativeModel('gemini-pro')
                self.ai_available = True
            except Exception as e:
                st.warning(f"⚠️ Gemini AI setup failed: {str(e)}")
                self.ai_available = False
        else:
            self.ai_available = False
        
        # Initialize Apify client
        if self.apify_token:
            try:
                from apify_client import ApifyClient
                self.apify_client = ApifyClient(self.apify_token)
                self.scraping_available = True
            except Exception as e:
                st.warning(f"⚠️ Apify setup failed: {str(e)}")
                self.scraping_available = False
        else:
            self.scraping_available = False
        
        # Popular hashtags for different categories
        self.hashtag_presets = {
            "Tech": ["#tech", "#technology", "#ai", "#machinelearning", "#coding", "#programming", 
                    "#developer", "#software", "#innovation", "#startup", "#techtrends", "#digitaltransformation"],
            "UI/UX Design": ["#ux", "#ui", "#design", "#userexperience", "#webdesign", "#appdesign", 
                           "#designthinking", "#prototype", "#wireframe", "#figma", "#sketch", "#adobe"],
            "Product Design": ["#productdesign", "#industrialdesign", "#design", "#innovation", 
                             "#designprocess", "#prototype", "#usercentered", "#designstrategy"],
            "AI": ["#ai", "#artificialintelligence", "#machinelearning", "#deeplearning", "#chatgpt", 
                  "#automation", "#neural", "#algorithm", "#aiart", "#generativeai"]
        }
        
        # Initialize session state
        if 'bookmarks' not in st.session_state:
            st.session_state.bookmarks = []
        if 'posts_data' not in st.session_state:
            st.session_state.posts_data = []

    def get_all_hashtags(self) -> List[str]:
        """Get all hashtags for multiselect"""
        all_hashtags = []
        for category_hashtags in self.hashtag_presets.values():
            all_hashtags.extend(category_hashtags)
        return sorted(list(set(all_hashtags)))

    def scrape_instagram_posts(self, hashtags: List[str], time_filter: str, post_type: str, limit: int = 50) -> List[Dict]:
        """Scrape Instagram posts using Apify API"""
        
        if not self.scraping_available:
            st.warning("⚠️ Apify not configured. Using demo data.")
            return self._get_demo_data(hashtags, time_filter, post_type, limit)
        
        try:
            # Configure Apify actor run
            actor_input = {
                "hashtags": hashtags,
                "resultsLimit": limit,
                "searchType": "hashtag",
                "addParentData": False
            }
            
            # Add time filter
            time_filters = {
                "Today": 1,
                "48 Hours": 2, 
                "4 Days": 4,
                "Week": 7,
                "Month": 30
            }
            
            days_back = time_filters.get(time_filter, 30)
            cutoff_date = datetime.now() - timedelta(days=days_back)
            actor_input["dateFrom"] = cutoff_date.isoformat()
            
            # Add proxy if available
            if self.proxy_url:
                actor_input["proxy"] = {"useApifyProxy": False, "proxyUrls": [self.proxy_url]}
            
            # Run Instagram scraper
            run = self.apify_client.actor("apify/instagram-hashtag-scraper").call(run_input=actor_input)
            
            # Get results
            posts_data = []
            for item in self.apify_client.dataset(run["defaultDatasetId"]).iterate_items():
                post_data = {
                    "id": item.get("id", ""),
                    "creator": item.get("ownerUsername", "unknown"),
                    "thumbnail": item.get("displayUrl", ""),
                    "likes": item.get("likesCount", 0),
                    "comments": item.get("commentsCount", 0),
                    "shares": item.get("videoViewCount", 0),  # Instagram doesn't have direct shares
                    "views": item.get("videoViewCount", item.get("likesCount", 0) * 10),
                    "caption": item.get("caption", ""),
                    "post_type": self._determine_post_type(item),
                    "url": f"https://instagram.com/p/{item.get('shortCode', '')}",
                    "timestamp": datetime.fromisoformat(item.get("timestamp", "").replace("Z", "+00:00")) if item.get("timestamp") else datetime.now(),
                    "hashtags": self._extract_hashtags(item.get("caption", ""))
                }
                posts_data.append(post_data)
            
            # Filter by post type
            if post_type != "all":
                posts_data = [post for post in posts_data if post["post_type"].lower() == post_type]
            
            return posts_data[:limit]
            
        except Exception as e:
            st.error(f"❌ Scraping failed: {str(e)}")
            return self._get_demo_data(hashtags, time_filter, post_type, limit)
    
    def _get_demo_data(self, hashtags: List[str], time_filter: str, post_type: str, limit: int) -> List[Dict]:
        """Generate demo data when API is not available"""
        mock_posts = [
            {
                "id": f"post_{i}",
                "creator": f"designer_{i % 10}",
                "thumbnail": f"https://picsum.photos/300/200?random={i}",
                "likes": 1500 + (i * 100),
                "comments": 45 + (i * 5),
                "shares": 20 + (i * 2),
                "views": 5000 + (i * 200),
                "caption": f"Amazing {hashtags[0] if hashtags else 'design'} inspiration! Check out this innovative approach to modern design solutions.",
                "post_type": post_type if post_type != "all" else ["posts", "carousels", "reels"][i % 3],
                "url": f"https://instagram.com/p/mock_{i}",
                "timestamp": datetime.now() - timedelta(days=i % 30),
                "hashtags": hashtags[:3] if hashtags else ["#design"]
            }
            for i in range(limit)
        ]
        
        # Filter by time
        time_filters = {
            "Today": 1,
            "48 Hours": 2,
            "4 Days": 4,
            "Week": 7,
            "Month": 30
        }
        
        days_back = time_filters.get(time_filter, 30)
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        filtered_posts = [
            post for post in mock_posts 
            if post["timestamp"] >= cutoff_date
        ]
        
        return filtered_posts
    
    def _determine_post_type(self, item: Dict) -> str:
        """Determine post type from Instagram data"""
        if item.get("videoUrl"):
            return "reels"
        elif item.get("sidecarMedias"):
            return "carousels"
        else:
            return "posts"
    
    def _extract_hashtags(self, caption: str) -> List[str]:
        """Extract hashtags from caption"""
        hashtags = re.findall(r'#\w+', caption)
        return hashtags[:5]  # Limit to 5 hashtags

    def analyze_with_gemini(self, caption: str, hashtags: List[str]) -> Dict:
        """Analyze post content with Gemini AI"""
        if not self.ai_available:
            return {
                "category": "General",
                "sentiment": "Positive",
                "engagement_prediction": "Medium",
                "content_quality": 75,
                "trending_potential": 60
            }
        
        try:
            prompt = f"""
            Analyze this Instagram post:
            Caption: {caption}
            Hashtags: {', '.join(hashtags)}
            
            Provide analysis in JSON format:
            {{
                "category": "Tech/UI-UX/Product Design/AI/Other",
                "sentiment": "Positive/Neutral/Negative",
                "engagement_prediction": "High/Medium/Low",
                "content_quality": <score 0-100>,
                "trending_potential": <score 0-100>
            }}
            """
            
            response = self.model.generate_content(prompt)
            return json.loads(response.text)
        except Exception as e:
            st.warning(f"⚠️ AI analysis failed: {str(e)}")
            return {
                "category": "General",
                "sentiment": "Positive", 
                "engagement_prediction": "Medium",
                "content_quality": 75,
                "trending_potential": 60
            }

    def bookmark_post(self, post_id: str):
        """Add post to bookmarks"""
        if post_id not in st.session_state.bookmarks:
            st.session_state.bookmarks.append(post_id)
            st.success("Post bookmarked!")
        else:
            st.session_state.bookmarks.remove(post_id)
            st.success("Bookmark removed!")

def main():
    analytics = InstagramAnalytics()
    
    # Check if API keys are configured
    if not analytics.secrets_manager.has_required_keys():
        if not analytics.secrets_manager.show_setup_wizard():
            st.stop()
    
    # Show API status in sidebar
    with st.sidebar:
        st.markdown("### 🔧 API Status")
        apify_status = "✅ Connected" if analytics.scraping_available else "❌ Not Connected"
        gemini_status = "✅ Connected" if analytics.ai_available else "❌ Not Connected"
        
        st.markdown(f"**Apify**: {apify_status}")
        st.markdown(f"**Gemini AI**: {gemini_status}")
        
        if st.button("⚙️ Manage API Keys"):
            st.session_state.show_api_setup = True
        
        if st.session_state.get('show_api_setup', False):
            analytics.secrets_manager.show_setup_wizard()
            if st.button("❌ Close Setup"):
                st.session_state.show_api_setup = False
                st.experimental_rerun()
        
        st.markdown("---")
    
    # Header
    st.markdown('<h1 class="main-header">📊 Instagram Analytics Dashboard</h1>', unsafe_allow_html=True)
    
    # Sidebar filters
    with st.sidebar:
        st.header("🔍 Filters & Search")
        
        # Hashtag search with presets
        st.subheader("Hashtags")
        selected_hashtags = st.multiselect(
            "Select hashtags to analyze:",
            options=analytics.get_all_hashtags(),
            default=["#ui", "#design", "#tech"],
            help="Start typing to see hashtag suggestions"
        )
        
        # Time filter
        time_filter = st.selectbox(
            "📅 Time Period",
            ["Today", "48 Hours", "4 Days", "Week", "Month"],
            index=4
        )
        
        # Post type filter
        post_type = st.selectbox(
            "📱 Content Type",
            ["All", "Posts", "Carousels", "Reels"],
            index=0
        )
        
        # Sort options
        sort_by = st.selectbox(
            "📈 Sort By",
            ["Likes", "Comments", "Shares", "Views", "Recent"],
            index=0
        )
        
        # Number of posts to load
        post_limit = st.slider("Posts to Load", 10, 100, 50)
        
        # Action buttons
        if st.button("🔄 Refresh Data", type="primary"):
            st.session_state.posts_data = []
        
        st.markdown("---")
        st.markdown(f"📌 **Bookmarks:** {len(st.session_state.bookmarks)}")
        
        if st.button("📋 View Bookmarks"):
            st.session_state.show_bookmarks = True

    # Main content area
    col1, col2, col3, col4 = st.columns(4)
    
    # Load and display posts
    if not st.session_state.posts_data or st.button("Load Posts"):
        with st.spinner("🔍 Analyzing Instagram posts..."):
            posts = analytics.scrape_instagram_posts(
                hashtags=selected_hashtags,
                time_filter=time_filter,
                post_type=post_type.lower() if post_type != "All" else "all",
                limit=post_limit
            )
            
            # Sort posts
            if sort_by == "Likes":
                posts.sort(key=lambda x: x["likes"], reverse=True)
            elif sort_by == "Comments":
                posts.sort(key=lambda x: x["comments"], reverse=True)
            elif sort_by == "Shares":
                posts.sort(key=lambda x: x["shares"], reverse=True)
            elif sort_by == "Views":
                posts.sort(key=lambda x: x["views"], reverse=True)
            elif sort_by == "Recent":
                posts.sort(key=lambda x: x["timestamp"], reverse=True)
            
            st.session_state.posts_data = posts

    # Display metrics
    if st.session_state.posts_data:
        total_posts = len(st.session_state.posts_data)
        avg_likes = sum(post["likes"] for post in st.session_state.posts_data) / total_posts
        avg_engagement = sum(post["likes"] + post["comments"] + post["shares"] 
                           for post in st.session_state.posts_data) / total_posts
        top_creator = max(st.session_state.posts_data, key=lambda x: x["likes"])["creator"]
        
        with col1:
            st.metric("📊 Total Posts", f"{total_posts:,}")
        with col2:
            st.metric("❤️ Avg Likes", f"{avg_likes:,.0f}")
        with col3:
            st.metric("🔥 Avg Engagement", f"{avg_engagement:,.0f}")
        with col4:
            st.metric("🏆 Top Creator", top_creator)

    # Display posts in grid layout
    if st.session_state.posts_data:
        st.markdown("---")
        st.subheader(f"📱 {len(st.session_state.posts_data)} Posts Found")
        
        # Create columns for grid layout
        cols = st.columns(3)
        
        for idx, post in enumerate(st.session_state.posts_data):
            col_idx = idx % 3
            
            with cols[col_idx]:
                # Post card
                st.markdown(f"""
                <div class="post-card">
                    <img src="{post['thumbnail']}" class="post-thumbnail" alt="Post thumbnail">
                    <div class="post-content">
                        <div class="creator-name">@{post['creator']}</div>
                        <p style="font-size: 0.8rem; color: #4b5563; margin: 0.5rem 0;">
                            {post['caption'][:100]}{'...' if len(post['caption']) > 100 else ''}
                        </p>
                        <div class="post-stats">
                            <span>❤️ {post['likes']:,}</span>
                            <span>💬 {post['comments']:,}</span>
                            <span>📤 {post['shares']:,}</span>
                            <span>👁️ {post['views']:,}</span>
                        </div>
                        <div style="margin-top: 0.5rem;">
                            {' '.join([f'<span class="hashtag-tag">{tag}</span>' for tag in post['hashtags'][:3]])}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Action buttons
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("🔗 View Post", key=f"view_{post['id']}"):
                        st.markdown(f"[Open Instagram Post]({post['url']})")
                
                with col_b:
                    bookmark_text = "🔖 Saved" if post['id'] in st.session_state.bookmarks else "📌 Save"
                    if st.button(bookmark_text, key=f"bookmark_{post['id']}"):
                        analytics.bookmark_post(post['id'])
                        st.experimental_rerun()
                
                st.markdown("---")

    # Show bookmarks if requested
    if st.session_state.get('show_bookmarks', False):
        st.subheader("📌 Your Bookmarks")
        if st.session_state.bookmarks:
            bookmarked_posts = [
                post for post in st.session_state.posts_data 
                if post['id'] in st.session_state.bookmarks
            ]
            
            for post in bookmarked_posts:
                with st.expander(f"@{post['creator']} - {post['likes']:,} likes"):
                    st.write(post['caption'])
                    st.markdown(f"[View on Instagram]({post['url']})")
        else:
            st.info("No bookmarks yet. Start bookmarking posts to see them here!")
        
        if st.button("❌ Close Bookmarks"):
            st.session_state.show_bookmarks = False
            st.experimental_rerun()

    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #6b7280; font-size: 0.8rem;">
        Built with ❤️ using Streamlit | Powered by Apify & Google Gemini
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
