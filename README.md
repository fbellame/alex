# Enhanced AI Voice Assistant for SmileRight Dental Clinic

## Overview

This enhanced AI voice assistant provides comprehensive patient management, appointment scheduling, and treatment information services for SmileRight Dental Clinic. The system now includes patient identification workflows, a knowledge base with treatment pricing, and calendar integration.

## New Features

### 1. Patient Identification & Management
- **Patient Detection**: Automatically determines if caller is new or returning patient
- **Patient Verification**: Verifies returning patients using phone number and date of birth
- **Patient Registration**: Creates new patient records with minimal required information
- **Patient Database**: Stores patient information securely with privacy considerations

### 2. Enhanced Agent Workflow
```
Greeter → PatientIdentificationAgent → {
    Returning Patient → PatientLookupAgent → {
        Found → BookingAgent/InfoAgent
        Not Found → RegistrationAgent
    }
    New Patient → RegistrationAgent → {
        Information Intent → InfoAgent
        Booking Intent → EnhancedBookingAgent
    }
}
```

### 3. Treatment Knowledge Base
- **Comprehensive Treatment Database**: 11 common dental treatments with pricing
- **Price Ranges**: Realistic pricing for Montreal dental market
- **Treatment Categories**: Preventive, diagnostic, restorative, endodontic, cosmetic, surgical, periodontal
- **Search Functionality**: Search treatments by keyword or category
- **Voice-Optimized Pricing**: Natural speech responses for treatment costs and duration
- **Fuzzy Matching**: Intelligent treatment name matching for user queries

### 4. Calendar Integration
- **Availability Checking**: Validates appointment times against clinic hours
- **Conflict Detection**: Prevents double-booking
- **Alternative Suggestions**: Offers alternative times when preferred slots unavailable
- **Business Hours Enforcement**: Monday-Friday 8AM-12PM, 1PM-6PM

## Agent Descriptions

### PatientIdentificationAgent
- **Purpose**: Determines if caller is new or returning patient
- **Key Question**: "Are you a new patient or have you visited our clinic before?"
- **Transfers**: Routes to PatientLookupAgent or RegistrationAgent

### PatientLookupAgent
- **Purpose**: Verifies returning patients
- **Required Info**: Phone number (1-XXX-XXX-XXXX) and date of birth (YYYY-MM-DD)
- **Actions**: Searches patient database, welcomes back if found
- **Fallback**: Offers new patient registration if not found

### RegistrationAgent
- **Purpose**: Registers new patients
- **Collects**: Name, phone, date of birth, email (optional)
- **Creates**: Patient record in database
- **Next Steps**: Determines intent (information vs booking)

### InfoAgent
- **Purpose**: Provides treatment information and pricing
- **Knowledge Base**: Access to complete treatment database
- **Capabilities**: Treatment search, pricing information, procedure details
- **Transfer**: Can route to booking if patient decides to schedule

### EnhancedBookingAgent
- **Purpose**: Schedules appointments for verified patients
- **Features**: Calendar integration, availability checking, appointment creation
- **Validation**: Ensures business hours compliance
- **Database**: Links appointments to patient records

## Treatment Database

| Treatment | Price Range | Duration | Category |
|-----------|-------------|----------|----------|
| Basic Cleaning | $120-150 | 45 min | Preventive |
| General Checkup | $80-100 | 30 min | Preventive |
| Bitewing X-rays | $25-40 each | 5 min | Diagnostic |
| Panoramic X-ray | $100-130 | 10 min | Diagnostic |
| Composite Filling | $150-250 | 30 min | Restorative |
| Amalgam Filling | $100-200 | 30 min | Restorative |
| Root Canal | $800-1200 | 90 min | Endodontic |
| Crown | $1000-1500 | 60 min | Restorative |
| Teeth Whitening | $300-500 | 90 min | Cosmetic |
| Tooth Extraction | $150-400 | 45 min | Surgical |
| Deep Cleaning | $200-300 | 60 min | Periodontal |

## Database Schema

### Patients Table
```sql
patients (
    patient_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT UNIQUE NOT NULL,  -- Format: 1-XXX-XXX-XXXX
    date_of_birth DATE,
    email TEXT,
    emergency_contact TEXT,
    registration_date TIMESTAMP,
    last_visit TIMESTAMP,
    status TEXT DEFAULT 'active'
)
```

### Appointments Table
```sql
appointments (
    appointment_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    appointment_date DATE NOT NULL,
    appointment_time TIME NOT NULL,
    treatment_type TEXT,
    status TEXT DEFAULT 'scheduled',
    notes TEXT,
    estimated_cost_range TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
```

### Treatments Table
```sql
treatments (
    treatment_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    price_range_min INTEGER,
    price_range_max INTEGER,
    duration_minutes INTEGER,
    category TEXT
)
```

## New Function Tools

### Patient Management
- `search_patient_by_phone_and_dob()`: Find existing patients
- `create_patient_record()`: Register new patients
- `update_date_of_birth()`: Collect DOB for verification
- `update_email()`: Collect optional email

### Knowledge Base
- `get_treatment_info()`: Get treatment details by name/category
- `search_treatments_by_keyword()`: Search treatments by keyword
- `get_treatment_price_and_duration()`: **NEW** - Get specific price and duration with voice-optimized responses

### Enhanced Treatment Pricing (NEW)
- `get_treatment_price_duration()`: Database method with fuzzy matching for treatment names
- `get_multiple_treatments_price_duration()`: Batch processing for multiple treatment queries

### Calendar Integration
- `check_availability()`: Verify appointment slot availability
- `suggest_alternative_times()`: Offer alternative appointment times

## Installation & Setup

### Prerequisites
```bash
pip install -r requirements.txt
```

### Database Initialization
The database will be automatically initialized with:
- Patient management tables
- Treatment knowledge base
- Default treatment data
- Proper indexes for performance

### Configuration
1. Set up environment variables in `.env`
2. Configure clinic hours in `calendar_service.py`
3. Adjust treatment pricing in database initialization

## Usage Examples

### New Patient Flow
1. **Greeter**: "Hello! Welcome to SmileRight Dental Clinic..."
2. **PatientIdentification**: "Are you a new patient or have you visited us before?"
3. **Registration**: "I'll need to collect some information. What's your full name?"
4. **Intent Detection**: "How can I help you today? Are you looking for information about treatments or would you like to book an appointment?"

### Returning Patient Flow
1. **Greeter**: "Hello! Welcome to SmileRight Dental Clinic..."
2. **PatientIdentification**: "Are you a new patient or have you visited us before?"
3. **PatientLookup**: "I'll need your phone number and date of birth to find your record."
4. **Verification**: "Welcome back, [Name]! How can I help you today?"

### Treatment Information Flow
1. **InfoAgent**: "I can help you with treatment information. What would you like to know about?"
2. **Search**: "I found several treatments related to 'cleaning'..."
3. **Details**: "Basic cleaning costs $120-150 and takes about 45 minutes..."

### Treatment Price & Duration Queries (NEW)
1. **Customer**: "How much does a root canal cost?"
2. **InfoAgent**: "For Root Canal, the cost is between 800 and 1200 dollars and the appointment typically takes 1 hour and 30 minutes. This treatment involves treatment for infected tooth pulp."
3. **Customer**: "What about a cleaning?"
4. **InfoAgent**: "For Basic Cleaning, the cost is between 120 and 150 dollars and the appointment typically takes 45 minutes. This treatment involves regular dental cleaning and polishing."

### Voice-Optimized Features
- **Natural Duration Format**: "1 hour and 30 minutes" instead of "90 minutes"
- **Conversational Pricing**: "between 120 and 150 dollars" instead of "$120-$150"
- **Fuzzy Matching**: "cleaning" matches "Basic Cleaning", "root canal" matches "Root Canal"
- **Context Tracking**: Stores requested treatment for seamless booking workflow

## Privacy & Security

### Patient Data Protection
- **Minimal Data Collection**: Only essential information stored
- **Secure Storage**: Encrypted database with proper access controls
- **Data Retention**: Configurable retention policies
- **Audit Trail**: Complete logging of all patient interactions

### Phone Number Format
- **Standard Format**: 1-XXX-XXX-XXXX
- **Validation**: Automatic format checking
- **Normalization**: Consistent storage format

## Performance Optimizations

### Database Optimizations
- **Batch Processing**: Queued operations for better performance
- **Indexes**: Optimized for common queries
- **Connection Pooling**: Efficient database connections
- **Background Processing**: Non-blocking operations

### Memory Management
- **In-Memory Metrics**: Fast access to session data
- **Lightweight Logging**: Minimal overhead
- **Efficient Caching**: Smart data caching strategies

## Monitoring & Analytics

### Metrics Collected
- Patient identification success rate
- Treatment information requests
- Appointment booking completion rate
- Agent transfer patterns
- Response times

### Logging
- Patient interactions (with privacy controls)
- Agent transfers and decisions
- Error tracking and debugging
- Performance metrics

## Future Enhancements

### Planned Features
1. **Google Calendar Integration**: Real-time calendar sync
2. **SMS Confirmations**: Automated appointment reminders
3. **Insurance Verification**: Insurance coverage checking
4. **Multi-language Support**: French and English support
5. **Advanced Scheduling**: Recurring appointments, waitlists

### Scalability Considerations
- **Multi-clinic Support**: Support for multiple clinic locations
- **Provider Scheduling**: Individual dentist calendars
- **Advanced Reporting**: Business intelligence and analytics
- **API Integration**: Third-party system integration

## Troubleshooting

### Common Issues
1. **Patient Not Found**: Verify phone number format and date of birth
2. **Appointment Conflicts**: Check calendar service initialization
3. **Database Errors**: Verify database permissions and connectivity
4. **Agent Transfer Issues**: Check agent registration in entrypoint

### Debug Mode
Enable detailed logging by setting `ENABLE_RECORDING = True` in the main file.

## Support

For technical support or questions about the enhanced AI voice assistant:
- Review the code documentation
- Check the troubleshooting section
- Examine the database logs for errors
- Test individual components in isolation

## License

This enhanced AI voice assistant is proprietary software for SmileRight Dental Clinic.
