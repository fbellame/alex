import aiosqlite
import asyncio
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager
import logging
from collections import deque
import threading
import time

logger = logging.getLogger("dental_assistant.db")

class AsyncDatabaseManager:
    def __init__(self, db_path: str = "dental_assistant.db", batch_size: int = 100, flush_interval: float = 5.0):
        self.db_path = db_path
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        
        # Batch processing queues
        self.transcript_queue = deque()
        self.metrics_queue = deque()
        self.user_data_queue = deque()
        
        # Background processing
        self.background_task = None
        self.should_stop = False
        
        # Initialize database
        self._init_db_sync()
        
    def _init_db_sync(self):
        """Initialize database synchronously for setup"""
        import sqlite3
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Enable WAL mode for better concurrency
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA cache_size=10000")
            cursor.execute("PRAGMA temp_store=MEMORY")
            
            # Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    room_id TEXT,
                    participant_id TEXT,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    duration_seconds INTEGER,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # User data table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    customer_name TEXT,
                    customer_phone TEXT,
                    booking_date_time TEXT,
                    booking_reason TEXT,
                    data_snapshot TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions (id)
                )
            """)
            
            # Conversation transcripts table with indexes
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transcripts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    agent_name TEXT,
                    role TEXT,
                    content TEXT,
                    message_id TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions (id)
                )
            """)
            
            # Metrics table with indexes
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    metric_type TEXT,
                    metric_name TEXT,
                    value REAL,
                    unit TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions (id)
                )
            """)
            
            # Agent transfers table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_transfers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    from_agent TEXT,
                    to_agent TEXT,
                    transfer_reason TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions (id)
                )
            """)
            
            # Patients table (minimal info for privacy)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS patients (
                    patient_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    phone TEXT UNIQUE NOT NULL,
                    date_of_birth DATE,
                    email TEXT,
                    emergency_contact TEXT,
                    registration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_visit TIMESTAMP,
                    status TEXT DEFAULT 'active'
                )
            """)
            
            # Appointments table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS appointments (
                    appointment_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL,
                    appointment_date DATE NOT NULL,
                    appointment_time TIME NOT NULL,
                    treatment_type TEXT,
                    status TEXT DEFAULT 'scheduled',
                    notes TEXT,
                    estimated_cost_range TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (patient_id) REFERENCES patients (patient_id)
                )
            """)
            
            # Treatment pricing knowledge base
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS treatments (
                    treatment_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    price_range_min INTEGER,
                    price_range_max INTEGER,
                    duration_minutes INTEGER,
                    category TEXT
                )
            """)
            
            # Create indexes for better performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_transcripts_session ON transcripts(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_session ON metrics(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_data_session ON user_data(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_patients_phone ON patients(phone)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_appointments_patient ON appointments(patient_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_appointments_date ON appointments(appointment_date)")
            
            # Insert default treatment data
            treatments_data = [
                ('basic_cleaning', 'Basic Cleaning', 'Regular dental cleaning and polishing', 120, 150, 45, 'preventive'),
                ('general_checkup', 'General Checkup', 'Comprehensive oral examination', 80, 100, 30, 'preventive'),
                ('bitewing_xray', 'Bitewing X-rays', 'X-rays to check for cavities between teeth', 25, 40, 5, 'diagnostic'),
                ('panoramic_xray', 'Panoramic X-ray', 'Full mouth X-ray for comprehensive view', 100, 130, 10, 'diagnostic'),
                ('composite_filling', 'Composite Filling', 'Tooth-colored filling material', 150, 250, 30, 'restorative'),
                ('amalgam_filling', 'Amalgam Filling', 'Silver filling material', 100, 200, 30, 'restorative'),
                ('root_canal', 'Root Canal', 'Treatment for infected tooth pulp', 800, 1200, 90, 'endodontic'),
                ('crown', 'Crown', 'Cap to restore damaged tooth', 1000, 1500, 60, 'restorative'),
                ('teeth_whitening', 'Teeth Whitening', 'Professional teeth whitening treatment', 300, 500, 90, 'cosmetic'),
                ('extraction', 'Tooth Extraction', 'Removal of damaged or problematic tooth', 150, 400, 45, 'surgical'),
                ('deep_cleaning', 'Deep Cleaning (per quadrant)', 'Scaling and root planing for gum disease', 200, 300, 60, 'periodontal')
            ]
            
            cursor.executemany("""
                INSERT OR IGNORE INTO treatments 
                (treatment_id, name, description, price_range_min, price_range_max, duration_minutes, category)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, treatments_data)
            
            conn.commit()
            logger.info("Database initialized successfully with optimizations and patient management")
    
    async def start_background_processing(self):
        """Start background batch processing"""
        if self.background_task is None:
            self.background_task = asyncio.create_task(self._background_processor())
    
    async def stop_background_processing(self):
        """Stop background processing and flush remaining data"""
        self.should_stop = True
        if self.background_task:
            await self.background_task
        await self._flush_all_queues()
    
    async def _background_processor(self):
        """Background task to process queued operations"""
        while not self.should_stop:
            try:
                await self._flush_all_queues()
                await asyncio.sleep(self.flush_interval)
            except Exception as e:
                logger.error(f"Background processing error: {e}")
                await asyncio.sleep(1)
    
    async def _flush_all_queues(self):
        """Flush all queues to database"""
        await asyncio.gather(
            self._flush_transcript_queue(),
            self._flush_metrics_queue(),
            self._flush_user_data_queue(),
            return_exceptions=True
        )
    
    @asynccontextmanager
    async def get_connection(self):
        """Async context manager for database connections"""
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        try:
            yield conn
        finally:
            await conn.close()
    
    async def create_session(self, room_id: str, participant_id: str) -> str:
        """Create a new session and return session ID"""
        session_id = str(uuid.uuid4())
        
        async with self.get_connection() as conn:
            await conn.execute("""
                INSERT INTO sessions (id, room_id, participant_id, start_time)
                VALUES (?, ?, ?, ?)
            """, (session_id, room_id, participant_id, datetime.now()))
            await conn.commit()
        
        logger.info(f"Created session: {session_id}")
        return session_id
    
    async def end_session(self, session_id: str, duration_seconds: int = None):
        """Mark session as ended"""
        async with self.get_connection() as conn:
            await conn.execute("""
                UPDATE sessions 
                SET end_time = ?, duration_seconds = ?, status = 'completed'
                WHERE id = ?
            """, (datetime.now(), duration_seconds, session_id))
            await conn.commit()
        
        logger.info(f"Ended session: {session_id}")
    
    def queue_user_data(self, session_id: str, user_data: 'UserData'):
        """Queue user data for batch processing (non-blocking)"""
        data_dict = {
            'customer_name': user_data.customer_name,
            'customer_phone': user_data.customer_phone,
            'booking_date_time': user_data.booking_date_time,
            'booking_reason': user_data.booking_reason
        }
        
        self.user_data_queue.append({
            'session_id': session_id,
            'customer_name': user_data.customer_name,
            'customer_phone': user_data.customer_phone,
            'booking_date_time': user_data.booking_date_time,
            'booking_reason': user_data.booking_reason,
            'data_snapshot': json.dumps(data_dict),
            'timestamp': datetime.now()
        })
    
    async def _flush_user_data_queue(self):
        """Flush user data queue to database"""
        if not self.user_data_queue:
            return
        
        batch = []
        while self.user_data_queue and len(batch) < self.batch_size:
            batch.append(self.user_data_queue.popleft())
        
        if batch:
            async with self.get_connection() as conn:
                await conn.executemany("""
                    INSERT OR REPLACE INTO user_data 
                    (session_id, customer_name, customer_phone, booking_date_time, 
                     booking_reason, data_snapshot, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, [(
                    item['session_id'],
                    item['customer_name'],
                    item['customer_phone'],
                    item['booking_date_time'],
                    item['booking_reason'],
                    item['data_snapshot'],
                    item['timestamp']
                ) for item in batch])
                await conn.commit()
    
    def queue_transcript(self, session_id: str, agent_name: str, role: str, 
                        content: str, message_id: str = None, metadata: Dict = None):
        """Queue transcript for batch processing (non-blocking)"""
        self.transcript_queue.append({
            'session_id': session_id,
            'agent_name': agent_name,
            'role': role,
            'content': content,
            'message_id': message_id or str(uuid.uuid4()),
            'metadata': json.dumps(metadata) if metadata else None,
            'timestamp': datetime.now()
        })
    
    async def _flush_transcript_queue(self):
        """Flush transcript queue to database"""
        if not self.transcript_queue:
            return
        
        batch = []
        while self.transcript_queue and len(batch) < self.batch_size:
            batch.append(self.transcript_queue.popleft())
        
        if batch:
            async with self.get_connection() as conn:
                await conn.executemany("""
                    INSERT INTO transcripts 
                    (session_id, agent_name, role, content, message_id, metadata, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, [(
                    item['session_id'],
                    item['agent_name'],
                    item['role'],
                    item['content'],
                    item['message_id'],
                    item['metadata'],
                    item['timestamp']
                ) for item in batch])
                await conn.commit()
    
    def queue_metric(self, session_id: str, metric_type: str, metric_name: str, 
                    value: float, unit: str = None, metadata: Dict = None):
        """Queue metric for batch processing (non-blocking)"""
        self.metrics_queue.append({
            'session_id': session_id,
            'metric_type': metric_type,
            'metric_name': metric_name,
            'value': value,
            'unit': unit,
            'metadata': json.dumps(metadata) if metadata else None,
            'timestamp': datetime.now()
        })
    
    async def _flush_metrics_queue(self):
        """Flush metrics queue to database"""
        if not self.metrics_queue:
            return
        
        batch = []
        while self.metrics_queue and len(batch) < self.batch_size:
            batch.append(self.metrics_queue.popleft())
        
        if batch:
            async with self.get_connection() as conn:
                await conn.executemany("""
                    INSERT INTO metrics 
                    (session_id, metric_type, metric_name, value, unit, metadata, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, [(
                    item['session_id'],
                    item['metric_type'],
                    item['metric_name'],
                    item['value'],
                    item['unit'],
                    item['metadata'],
                    item['timestamp']
                ) for item in batch])
                await conn.commit()
    
    async def save_agent_transfer(self, session_id: str, from_agent: str, 
                                 to_agent: str, reason: str = None):
        """Save agent transfer immediately (these are less frequent)"""
        async with self.get_connection() as conn:
            await conn.execute("""
                INSERT INTO agent_transfers 
                (session_id, from_agent, to_agent, transfer_reason)
                VALUES (?, ?, ?, ?)
            """, (session_id, from_agent, to_agent, reason))
            await conn.commit()
    
    async def get_session_data(self, session_id: str) -> Dict[str, Any]:
        """Get complete session data"""
        async with self.get_connection() as conn:
            # Get session info
            cursor = await conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            session = await cursor.fetchone()
            
            if not session:
                return None
            
            # Get user data
            cursor = await conn.execute("SELECT * FROM user_data WHERE session_id = ?", (session_id,))
            user_data = await cursor.fetchone()
            
            # Get transcripts
            cursor = await conn.execute("""
                SELECT * FROM transcripts 
                WHERE session_id = ? 
                ORDER BY timestamp
            """, (session_id,))
            transcripts = await cursor.fetchall()
            
            # Get metrics
            cursor = await conn.execute("SELECT * FROM metrics WHERE session_id = ?", (session_id,))
            metrics = await cursor.fetchall()
            
            # Get agent transfers
            cursor = await conn.execute("""
                SELECT * FROM agent_transfers 
                WHERE session_id = ? 
                ORDER BY timestamp
            """, (session_id,))
            transfers = await cursor.fetchall()
            
            return {
                'session': dict(session),
                'user_data': dict(user_data) if user_data else None,
                'transcripts': [dict(t) for t in transcripts],
                'metrics': [dict(m) for m in metrics],
                'agent_transfers': [dict(t) for t in transfers]
            }
    
    # Patient Management Methods
    async def search_patient_by_phone_and_dob(self, phone: str, date_of_birth: str) -> Optional[Dict[str, Any]]:
        """Search for patient by phone number and date of birth"""
        async with self.get_connection() as conn:
            cursor = await conn.execute("""
                SELECT * FROM patients 
                WHERE phone = ? AND date_of_birth = ? AND status = 'active'
            """, (phone, date_of_birth))
            patient = await cursor.fetchone()
            
            if patient:
                # Update last visit timestamp
                await conn.execute("""
                    UPDATE patients SET last_visit = ? WHERE patient_id = ?
                """, (datetime.now(), patient['patient_id']))
                await conn.commit()
                
                return dict(patient)
            return None
    
    async def create_patient_record(self, name: str, phone: str, date_of_birth: str, 
                                  email: str = None, emergency_contact: str = None) -> str:
        """Create a new patient record and return patient ID"""
        patient_id = str(uuid.uuid4())
        
        async with self.get_connection() as conn:
            await conn.execute("""
                INSERT INTO patients 
                (patient_id, name, phone, date_of_birth, email, emergency_contact, registration_date, last_visit)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (patient_id, name, phone, date_of_birth, email, emergency_contact, 
                  datetime.now(), datetime.now()))
            await conn.commit()
        
        logger.info(f"Created patient record: {patient_id} for {name}")
        return patient_id
    
    async def get_patient_appointment_history(self, patient_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get patient's appointment history"""
        async with self.get_connection() as conn:
            cursor = await conn.execute("""
                SELECT * FROM appointments 
                WHERE patient_id = ? 
                ORDER BY appointment_date DESC, appointment_time DESC
                LIMIT ?
            """, (patient_id, limit))
            appointments = await cursor.fetchall()
            
            return [dict(apt) for apt in appointments]
    
    async def create_appointment(self, patient_id: str, appointment_date: str, 
                               appointment_time: str, treatment_type: str = None,
                               notes: str = None, estimated_cost_range: str = None) -> str:
        """Create a new appointment and return appointment ID"""
        appointment_id = str(uuid.uuid4())
        
        async with self.get_connection() as conn:
            await conn.execute("""
                INSERT INTO appointments 
                (appointment_id, patient_id, appointment_date, appointment_time, 
                 treatment_type, notes, estimated_cost_range)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (appointment_id, patient_id, appointment_date, appointment_time,
                  treatment_type, notes, estimated_cost_range))
            await conn.commit()
        
        logger.info(f"Created appointment: {appointment_id} for patient {patient_id}")
        return appointment_id
    
    # Treatment Knowledge Base Methods
    async def get_treatment_info(self, treatment_name: str = None, category: str = None) -> List[Dict[str, Any]]:
        """Get treatment information by name or category"""
        async with self.get_connection() as conn:
            if treatment_name:
                cursor = await conn.execute("""
                    SELECT * FROM treatments 
                    WHERE name LIKE ? OR treatment_id LIKE ?
                """, (f"%{treatment_name}%", f"%{treatment_name}%"))
            elif category:
                cursor = await conn.execute("""
                    SELECT * FROM treatments WHERE category = ?
                """, (category,))
            else:
                cursor = await conn.execute("SELECT * FROM treatments ORDER BY category, name")
            
            treatments = await cursor.fetchall()
            return [dict(t) for t in treatments]
    
    async def get_treatment_pricing(self, treatment_id: str) -> Optional[Dict[str, Any]]:
        """Get specific treatment pricing information"""
        async with self.get_connection() as conn:
            cursor = await conn.execute("""
                SELECT * FROM treatments WHERE treatment_id = ?
            """, (treatment_id,))
            treatment = await cursor.fetchone()
            
            return dict(treatment) if treatment else None
    
    async def search_treatments_by_keyword(self, keyword: str) -> List[Dict[str, Any]]:
        """Search treatments by keyword in name or description"""
        async with self.get_connection() as conn:
            cursor = await conn.execute("""
                SELECT * FROM treatments 
                WHERE name LIKE ? OR description LIKE ?
                ORDER BY name
            """, (f"%{keyword}%", f"%{keyword}%"))
            treatments = await cursor.fetchall()
            
            return [dict(t) for t in treatments]


class OptimizedMetricsCollector:
    """Lightweight metrics collector with sampling and filtering"""
    
    def __init__(self, db_manager: AsyncDatabaseManager, session_id: str, 
                 sample_rate: float = 0.1, latency_threshold: float = 0.1):
        self.db_manager = db_manager
        self.session_id = session_id
        self.sample_rate = sample_rate  # Only sample 10% of metrics
        self.latency_threshold = latency_threshold  # Only log high latencies
        self.metric_counts = {}  # Track metric frequency
        
    def should_collect_metric(self, metric_name: str) -> bool:
        """Determine if we should collect this metric"""
        # Always collect critical metrics
        critical_metrics = [
            'session_duration',
            'agent_transfer',
            'error_rate',
            'booking_completion'
        ]
        
        if metric_name in critical_metrics:
            return True
        
        # Sample other metrics
        import random
        return random.random() < self.sample_rate
    
    def collect_metric(self, metric_type: str, metric_name: str, value: float, 
                      unit: str = None, metadata: Dict = None):
        """Collect metric with intelligent filtering"""
        if not self.should_collect_metric(metric_name):
            return
        
        # Skip low-value latency metrics
        if 'latency' in metric_name.lower() and value < self.latency_threshold:
            return
        
        # Queue for batch processing
        self.db_manager.queue_metric(
            self.session_id, metric_type, metric_name, value, unit, metadata
        )


# Lightweight in-memory metrics for real-time monitoring
class InMemoryMetrics:
    def __init__(self):
        self.metrics = {}
        self.last_update = time.time()
        
    def update(self, key: str, value: float):
        """Update metric in memory only"""
        self.metrics[key] = {
            'value': value,
            'timestamp': time.time()
        }
        self.last_update = time.time()
    
    def get_summary(self) -> Dict[str, Any]:
        """Get current metrics summary"""
        return {
            'metrics': self.metrics,
            'last_update': self.last_update,
            'total_metrics': len(self.metrics)
        }
