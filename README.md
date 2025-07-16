# Alex - AI Voice Dental Clinic Assistant 🦷🤖

Alex is an intelligent voice assistant designed specifically for dental clinics to handle appointment bookings and customer inquiries through natural voice conversations. Built with LiveKit's real-time communication platform, Alex provides a seamless, human-like interaction experience for dental clinic patients.

## 🌟 Features

### Core Functionality
- **Real-time Voice Conversations**: Natural speech-to-speech interactions using advanced AI
- **Appointment Booking**: Complete booking workflow with customer information collection
- **Multi-Agent System**: Intelligent conversation flow between specialized agents
- **Business Hours Validation**: Automatically validates appointments against clinic operating hours
- **Customer Data Management**: Securely collects and stores customer information

### Technical Capabilities
- **Advanced Speech Processing**: 
  - OpenAI GPT-4o-mini for natural language understanding
  - Deepgram Nova-3 for accurate speech recognition
  - OpenAI TTS with natural voice synthesis
- **Real-time Features**:
  - Voice activity detection (VAD)
  - Noise cancellation
  - Multilingual turn detection
- **Performance Optimizations**:
  - Async database operations with batch processing
  - In-memory metrics for real-time monitoring
  - Optimized conversation logging
- **Comprehensive Logging**:
  - Full conversation transcripts
  - Performance metrics collection
  - Agent transfer tracking
  - Session analytics

### Clinic Information
- **SmileRight Dental Clinic**
- **Location**: 5561 St-Denis Street, Montreal, Canada
- **Hours**: Monday to Friday, 8:00 AM - 12:00 PM and 1:00 PM - 6:00 PM
- **Closed**: Weekends

## 🚀 Installation

### Prerequisites
- Python 3.10
- Conda (Anaconda or Miniconda)
- API keys for OpenAI, Deepgram, and LiveKit

### Step 1: Create Conda Environment

```bash
# Create a new conda environment with Python 3.10
conda create -n alex-dental python=3.10 -y

# Activate the environment
conda activate alex-dental
```

### Step 2: Clone and Setup Project

```bash
# Navigate to your projects directory
cd /path/to/your/projects

# Clone or download the project files
# Ensure you have the following files:
# - alex_agent.py
# - db_manager.py
# - requirements.txt
```

### Step 3: Install Dependencies

```bash
# Install all required packages
pip install -r requirements.txt
```

The requirements include:
- `python-dotenv` - Environment variable management
- `livekit-agents[deepgram,openai,cartesia,silero,turn-detector]~=1.0` - LiveKit agents with plugins
- `livekit-plugins-noise-cancellation~=0.2` - Noise cancellation
- `aiosqlite` - Async SQLite database
- `db-sqlite3` - SQLite database support
- `pandas` - Data analysis
- `matplotlib` - Plotting
- `seaborn` - Statistical visualization
- `pyyaml` - YAML configuration

### Step 4: Environment Configuration

Create a `.env` file in your project directory:

```bash
# Create environment file
touch .env
```

Add the following environment variables to your `.env` file:

```env
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Deepgram Configuration  
DEEPGRAM_API_KEY=your_deepgram_api_key_here

# LiveKit Configuration
LIVEKIT_URL=your_livekit_server_url
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret

# Optional: Database path (defaults to dental_assistant.db)
DATABASE_PATH=dental_assistant.db
```

### Step 5: API Key Setup

#### OpenAI API Key
1. Visit [OpenAI Platform](https://platform.openai.com/)
2. Create an account or sign in
3. Navigate to API Keys section
4. Create a new API key
5. Add to your `.env` file

#### Deepgram API Key
1. Visit [Deepgram Console](https://console.deepgram.com/)
2. Create an account or sign in
3. Navigate to API Keys
4. Create a new API key
5. Add to your `.env` file

#### LiveKit Configuration
1. Visit [LiveKit Cloud](https://cloud.livekit.io/) or set up your own LiveKit server
2. Create a project
3. Get your API key, secret, and server URL
4. Add to your `.env` file

## 🎯 Usage

### Basic Usage

```bash
# Activate the conda environment
conda activate alex-dental

# Run the dental assistant
python alex_agent.py
```

### Advanced Usage

#### Disable Database Recording
```bash
# Run without conversation/metrics logging
python alex_agent.py --no-recording
```

#### Command Line Options
- `--no-recording` or `--disable-recording`: Disable database logging for privacy or testing

### Agent Workflow

1. **Greeter Agent**: 
   - Welcomes patients
   - Provides clinic information
   - Handles general inquiries
   - Transfers to booking agent when needed

2. **Booking Agent**:
   - Collects customer name
   - Requests phone number
   - Schedules appointment date/time
   - Records booking reason
   - Validates against business hours
   - Confirms reservation details

## 🏗️ Architecture

### Agent System
```
┌─────────────────┐    Transfer    ┌─────────────────┐
│   Greeter       │ ──────────────▶│ Booking Agent   │
│   Agent         │                │                 │
│                 │                │ - Name          │
│ - Welcome       │                │ - Phone         │
│ - Clinic Info   │                │ - Date/Time     │
│ - General Help  │                │ - Reason        │
└─────────────────┘                └─────────────────┘
```

### Technology Stack
```
┌─────────────────────────────────────────────────────┐
│                   Alex Assistant                    │
├─────────────────────────────────────────────────────┤
│ Speech-to-Text: Deepgram Nova-3                     │
│ Language Model: OpenAI GPT-4o-mini                  │
│ Text-to-Speech: OpenAI TTS                          │
├─────────────────────────────────────────────────────┤
│ Real-time Communication: LiveKit                    │
│ Database: SQLite with async operations              │
│ Voice Processing: Silero VAD + Noise Cancellation  │
└─────────────────────────────────────────────────────┘
```

## 💾 Database Schema

The assistant automatically creates and manages a SQLite database with the following tables:

- **sessions**: Call session tracking
- **user_data**: Customer information
- **transcripts**: Full conversation logs
- **metrics**: Performance and usage metrics
- **agent_transfers**: Agent handoff tracking

## 🔧 Configuration

### Clinic Settings
To customize for your clinic, modify the following in `alex_agent.py`:

```python
# Clinic information
clinic_name = "SmileRight Dental Clinic"
clinic_address = "5561 St-Denis Street, Montreal, Canada"
clinic_hours = "Monday to Friday from 8:00 AM to 12:00 PM and 1:00 PM to 6:00 PM"
```

### Voice Settings
Customize voice characteristics:

```python
# TTS voice options: alloy, echo, fable, onyx, nova, shimmer
tts=openai.TTS(voice="ash")  # Change voice here
```

## 📊 Monitoring and Analytics

### Real-time Metrics
- Response times
- Agent transfers
- Booking completion rates
- Session duration
- Error tracking

### Database Analytics
Use the included analytics tools to analyze:
- Customer interaction patterns
- Peak booking times
- Agent performance
- Conversation quality

## 🛠️ Troubleshooting

### Common Issues

#### 1. Import Errors
```bash
# Ensure all dependencies are installed
pip install -r requirements.txt

# Check if conda environment is activated
conda activate alex-dental
```

#### 2. API Key Issues
```bash
# Verify .env file exists and contains valid keys
cat .env

# Test API connectivity
python -c "import openai; print('OpenAI key loaded')"
```

#### 3. Database Errors
```bash
# Check database permissions
ls -la dental_assistant.db

# Reset database (caution: deletes all data)
rm dental_assistant.db
python alex_agent.py  # Will recreate database
```

#### 4. Audio Issues
- Ensure microphone permissions are granted
- Check system audio settings
- Verify LiveKit server connectivity

### Performance Optimization

#### For High-Volume Usage
1. **Database Optimization**:
   ```python
   # Increase batch sizes in db_manager.py
   db_manager = AsyncDatabaseManager(batch_size=200, flush_interval=1.0)
   ```

2. **Memory Management**:
   ```python
   # Reduce metrics sampling
   metrics_collector = OptimizedMetricsCollector(sample_rate=0.05)
   ```

3. **Disable Recording for Testing**:
   ```bash
   python alex_agent.py --no-recording
   ```

## 🔒 Security and Privacy

- All conversations can be optionally logged to local SQLite database
- No data is sent to third parties beyond required API calls
- Customer information is stored locally and encrypted in transit
- Use `--no-recording` flag to disable all logging for maximum privacy

## 📝 Development

### Adding New Features

1. **New Function Tools**: Add to the respective agent class
2. **New Agents**: Extend `BaseAgent` class
3. **Database Schema**: Modify `db_manager.py`
4. **Custom Instructions**: Update agent initialization

### Testing

```bash
# Run with recording disabled for testing
python alex_agent.py --no-recording

# Monitor logs
tail -f dental_assistant.log
```

## 📄 License

This project is provided as-is for educational and commercial use. Please ensure compliance with your local healthcare and privacy regulations when deploying in production.

## 🤝 Support

For technical support or customization requests:
1. Check the troubleshooting section above
2. Review the LiveKit documentation
3. Verify API key configurations
4. Check system requirements and dependencies

---

**Built with ❤️ for modern dental practices**
