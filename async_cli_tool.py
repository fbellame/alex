#!/usr/bin/env python3
"""
CLI tool for managing and analyzing LiveKit dental assistant data
Updated for AsyncDatabaseManager
"""

import argparse
import sys
import asyncio
from datetime import datetime, timedelta
import json
import sqlite3
from db_manager import AsyncDatabaseManager
from typing import List, Dict, Any, Optional

class AsyncDataAnalyzer:
    """Data analyzer that works with AsyncDatabaseManager"""
    
    def __init__(self, db_path: str):
        self.db_manager = AsyncDatabaseManager(db_path)
        self.db_path = db_path
    
    async def search_sessions(self, customer_name: str = None, customer_phone: str = None,
                             date_from: datetime = None, date_to: datetime = None,
                             status: str = None) -> List[Dict[str, Any]]:
        """Search sessions with filters"""
        async with self.db_manager.get_connection() as conn:
            query = """
                SELECT s.*, u.customer_name, u.customer_phone, u.booking_date_time, u.booking_reason
                FROM sessions s
                LEFT JOIN user_data u ON s.id = u.session_id
                WHERE 1=1
            """
            params = []
            
            if customer_name:
                query += " AND u.customer_name LIKE ?"
                params.append(f"%{customer_name}%")
            
            if customer_phone:
                query += " AND u.customer_phone LIKE ?"
                params.append(f"%{customer_phone}%")
            
            if date_from:
                query += " AND s.start_time >= ?"
                params.append(date_from.isoformat())
            
            if date_to:
                query += " AND s.start_time <= ?"
                params.append(date_to.isoformat())
            
            if status:
                query += " AND s.status = ?"
                params.append(status)
            
            query += " ORDER BY s.start_time DESC"
            
            cursor = await conn.execute(query, params)
            sessions = await cursor.fetchall()
            return [dict(session) for session in sessions]
    
    async def get_performance_metrics(self, days: int) -> Dict[str, Any]:
        """Get performance metrics for the last N days"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        async with self.db_manager.get_connection() as conn:
            # Total sessions
            cursor = await conn.execute("""
                SELECT COUNT(*) as total_sessions
                FROM sessions
                WHERE start_time >= ?
            """, (start_date.isoformat(),))
            total_sessions = (await cursor.fetchone())[0]
            
            # Successful bookings (sessions with user data)
            cursor = await conn.execute("""
                SELECT COUNT(*) as successful_bookings
                FROM sessions s
                JOIN user_data u ON s.id = u.session_id
                WHERE s.start_time >= ? AND u.customer_name IS NOT NULL
            """, (start_date.isoformat(),))
            successful_bookings = (await cursor.fetchone())[0]
            
            # Average session duration
            cursor = await conn.execute("""
                SELECT AVG(duration_seconds) as avg_duration
                FROM sessions
                WHERE start_time >= ? AND duration_seconds IS NOT NULL
            """, (start_date.isoformat(),))
            avg_duration = (await cursor.fetchone())[0] or 0
            
            # Daily breakdown
            cursor = await conn.execute("""
                SELECT 
                    DATE(start_time) as date,
                    COUNT(*) as sessions,
                    COUNT(u.customer_name) as successful
                FROM sessions s
                LEFT JOIN user_data u ON s.id = u.session_id
                WHERE s.start_time >= ?
                GROUP BY DATE(start_time)
                ORDER BY date
            """, (start_date.isoformat(),))
            daily_data = await cursor.fetchall()
            
            daily_breakdown = {}
            for row in daily_data:
                daily_breakdown[row[0]] = {
                    'sessions': row[1],
                    'successful': row[2]
                }
            
            return {
                'total_sessions': total_sessions,
                'successful_bookings': successful_bookings,
                'success_rate': successful_bookings / total_sessions if total_sessions > 0 else 0,
                'avg_session_duration': avg_duration,
                'daily_breakdown': daily_breakdown
            }
    
    async def get_customer_interaction_analysis(self) -> Dict[str, Any]:
        """Analyze customer interactions"""
        async with self.db_manager.get_connection() as conn:
            # Role distribution
            cursor = await conn.execute("""
                SELECT role, COUNT(*) as count
                FROM transcripts
                GROUP BY role
            """)
            role_distribution = {row[0]: row[1] for row in await cursor.fetchall()}
            
            # Agent distribution
            cursor = await conn.execute("""
                SELECT agent_name, COUNT(*) as count
                FROM transcripts
                WHERE agent_name IS NOT NULL
                GROUP BY agent_name
            """)
            agent_distribution = {row[0]: row[1] for row in await cursor.fetchall()}
            
            # Session analysis
            cursor = await conn.execute("""
                SELECT 
                    s.id,
                    s.duration_seconds,
                    CASE WHEN u.customer_name IS NOT NULL THEN 1 ELSE 0 END as successful
                FROM sessions s
                LEFT JOIN user_data u ON s.id = u.session_id
                WHERE s.duration_seconds IS NOT NULL
            """)
            session_data = await cursor.fetchall()
            
            successful_sessions = [row for row in session_data if row[2] == 1]
            unsuccessful_sessions = [row for row in session_data if row[2] == 0]
            
            success_rate = len(successful_sessions) / len(session_data) if session_data else 0
            avg_duration_successful = sum(row[1] for row in successful_sessions) / len(successful_sessions) if successful_sessions else 0
            avg_duration_unsuccessful = sum(row[1] for row in unsuccessful_sessions) / len(unsuccessful_sessions) if unsuccessful_sessions else 0
            
            return {
                'role_distribution': role_distribution,
                'agent_distribution': agent_distribution,
                'session_analysis': {
                    'success_rate': success_rate,
                    'avg_duration_successful': avg_duration_successful,
                    'avg_duration_unsuccessful': avg_duration_unsuccessful
                }
            }
    
    async def export_session_transcript(self, session_id: str) -> str:
        """Export session transcript as formatted text"""
        session_data = await self.db_manager.get_session_data(session_id)
        
        if not session_data:
            return "Session not found"
        
        session = session_data['session']
        user_data = session_data['user_data']
        transcripts = session_data['transcripts']
        
        output = []
        output.append("=" * 80)
        output.append(f"SESSION TRANSCRIPT: {session_id}")
        output.append("=" * 80)
        output.append(f"Start Time: {session['start_time']}")
        output.append(f"Duration: {session['duration_seconds']}s" if session['duration_seconds'] else "Duration: N/A")
        output.append(f"Status: {session['status']}")
        
        if user_data:
            output.append(f"Customer: {user_data['customer_name']}")
            output.append(f"Phone: {user_data['customer_phone']}")
            output.append(f"Booking: {user_data['booking_date_time']}")
            output.append(f"Reason: {user_data['booking_reason']}")
        
        output.append("-" * 80)
        output.append("CONVERSATION:")
        output.append("-" * 80)
        
        for transcript in transcripts:
            timestamp = transcript['timestamp'][:19] if transcript['timestamp'] else 'N/A'
            agent = transcript['agent_name'] or 'Unknown'
            role = transcript['role']
            content = transcript['content']
            
            output.append(f"[{timestamp}] {agent} ({role}): {content}")
        
        return "\n".join(output)
    
    async def get_metrics_for_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Get metrics for a specific session"""
        async with self.db_manager.get_connection() as conn:
            cursor = await conn.execute("""
                SELECT * FROM metrics
                WHERE session_id = ?
                ORDER BY timestamp
            """, (session_id,))
            metrics = await cursor.fetchall()
            return [dict(metric) for metric in metrics]

def run_async(coro):
    """Helper to run async functions in sync context"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)

async def print_session_report(session_id: str, db_path: str = "dental_assistant.db"):
    """Print a formatted session report"""
    db_manager = AsyncDatabaseManager(db_path)
    session_data = await db_manager.get_session_data(session_id)
    
    if not session_data:
        print("Session not found")
        return
    
    session = session_data['session']
    user_data = session_data['user_data']
    transcripts = session_data['transcripts']
    metrics = session_data['metrics']
    transfers = session_data['agent_transfers']
    
    print(f"\n{'='*80}")
    print(f"SESSION REPORT: {session_id}")
    print(f"{'='*80}")
    
    print(f"Room ID: {session['room_id']}")
    print(f"Participant: {session['participant_id']}")
    print(f"Start Time: {session['start_time']}")
    print(f"End Time: {session['end_time'] or 'N/A'}")
    print(f"Duration: {session['duration_seconds']}s" if session['duration_seconds'] else "Duration: N/A")
    print(f"Status: {session['status']}")
    
    if user_data:
        print(f"\nCUSTOMER INFORMATION:")
        print(f"Name: {user_data['customer_name']}")
        print(f"Phone: {user_data['customer_phone']}")
        print(f"Booking Date/Time: {user_data['booking_date_time']}")
        print(f"Booking Reason: {user_data['booking_reason']}")
    
    print(f"\nCONVERSATION STATS:")
    print(f"Total Messages: {len(transcripts)}")
    
    if transcripts:
        role_counts = {}
        for transcript in transcripts:
            role = transcript['role']
            role_counts[role] = role_counts.get(role, 0) + 1
        
        for role, count in role_counts.items():
            print(f"  {role}: {count}")
    
    if transfers:
        print(f"\nAGENT TRANSFERS:")
        for transfer in transfers:
            print(f"  {transfer['timestamp'][:19]}: {transfer['from_agent']} → {transfer['to_agent']}")
            if transfer['transfer_reason']:
                print(f"    Reason: {transfer['transfer_reason']}")
    
    if metrics:
        print(f"\nMETRICS SUMMARY:")
        print(f"Total Metrics: {len(metrics)}")
        metric_types = {}
        for metric in metrics:
            metric_type = metric['metric_type']
            metric_types[metric_type] = metric_types.get(metric_type, 0) + 1
        
        for metric_type, count in metric_types.items():
            print(f"  {metric_type}: {count}")

async def list_recent_sessions(days: int = 7, db_path: str = "dental_assistant.db"):
    """List recent sessions"""
    analyzer = AsyncDataAnalyzer(db_path)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    sessions = await analyzer.search_sessions(date_from=start_date, date_to=end_date)
    
    print(f"\n{'='*100}")
    print(f"RECENT SESSIONS (Last {days} days) - {len(sessions)} found")
    print(f"{'='*100}")
    print(f"{'ID':<36} {'Date':<20} {'Duration':<10} {'Customer':<20} {'Phone':<15}")
    print("-" * 100)
    
    for session in sessions:
        session_id = session['id']
        start_time = session['start_time'][:19] if session['start_time'] else 'N/A'
        duration = f"{session['duration_seconds']}s" if session['duration_seconds'] else 'N/A'
        customer = session['customer_name'] or 'Unknown'
        phone = session['customer_phone'] or 'N/A'
        
        print(f"{session_id:<36} {start_time:<20} {duration:<10} {customer:<20} {phone:<15}")

def main():
    parser = argparse.ArgumentParser(description='LiveKit Dental Assistant Data Management Tool')
    parser.add_argument('--db', default='dental_assistant.db', help='Database path')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List sessions command
    list_parser = subparsers.add_parser('list', help='List recent sessions')
    list_parser.add_argument('--days', type=int, default=7, help='Number of days to look back')
    list_parser.add_argument('--status', choices=['all', 'completed', 'active'], default='all', help='Filter by status')
    
    # Show session command
    show_parser = subparsers.add_parser('show', help='Show detailed session information')
    show_parser.add_argument('session_id', help='Session ID to display')
    show_parser.add_argument('--format', choices=['summary', 'full', 'transcript'], default='summary', help='Output format')
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Search sessions')
    search_parser.add_argument('--name', help='Customer name (partial match)')
    search_parser.add_argument('--phone', help='Customer phone (partial match)')
    search_parser.add_argument('--days', type=int, default=30, help='Number of days to look back')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show statistics')
    stats_parser.add_argument('--days', type=int, default=7, help='Number of days to analyze')
    stats_parser.add_argument('--daily', action='store_true', help='Show daily breakdown')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export session data')
    export_parser.add_argument('session_id', help='Session ID to export')
    export_parser.add_argument('--format', choices=['txt', 'json'], default='txt', help='Export format')
    export_parser.add_argument('--output', help='Output file path')
    
    # Metrics command
    metrics_parser = subparsers.add_parser('metrics', help='Show metrics for a session')
    metrics_parser.add_argument('session_id', help='Session ID')
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser('cleanup', help='Clean up old data')
    cleanup_parser.add_argument('--days', type=int, default=90, help='Keep data newer than N days')
    cleanup_parser.add_argument('--confirm', action='store_true', help='Confirm deletion')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == 'list':
            run_async(list_sessions_cmd(args))
        elif args.command == 'show':
            run_async(show_session_cmd(args))
        elif args.command == 'search':
            run_async(search_sessions_cmd(args))
        elif args.command == 'stats':
            run_async(stats_cmd(args))
        elif args.command == 'export':
            run_async(export_cmd(args))
        elif args.command == 'metrics':
            run_async(metrics_cmd(args))
        elif args.command == 'cleanup':
            run_async(cleanup_cmd(args))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

async def list_sessions_cmd(args):
    """List recent sessions"""
    analyzer = AsyncDataAnalyzer(args.db)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=args.days)
    
    sessions = await analyzer.search_sessions(date_from=start_date, date_to=end_date)
    
    if args.status != 'all':
        sessions = [s for s in sessions if s['status'] == args.status]
    
    print(f"\n{'='*100}")
    print(f"SESSIONS (Last {args.days} days) - {len(sessions)} found")
    print(f"{'='*100}")
    print(f"{'ID':<36} {'Date':<20} {'Duration':<10} {'Status':<10} {'Customer':<20} {'Phone':<15}")
    print("-" * 100)
    
    for session in sessions:
        session_id = session['id']
        start_time = session['start_time'][:19] if session['start_time'] else 'N/A'
        duration = f"{session['duration_seconds']}s" if session['duration_seconds'] else 'N/A'
        status = "✓" if session['customer_name'] else "✗"
        customer = session['customer_name'] or 'Unknown'
        phone = session['customer_phone'] or 'N/A'
        
        print(f"{session_id:<36} {start_time:<20} {duration:<10} {status:<10} {customer:<20} {phone:<15}")

async def show_session_cmd(args):
    """Show detailed session information"""
    if args.format == 'summary':
        await print_session_report(args.session_id, args.db)
    elif args.format == 'transcript':
        analyzer = AsyncDataAnalyzer(args.db)
        transcript = await analyzer.export_session_transcript(args.session_id)
        print(transcript)
    elif args.format == 'full':
        db_manager = AsyncDatabaseManager(args.db)
        session_data = await db_manager.get_session_data(args.session_id)
        if session_data:
            print(json.dumps(session_data, indent=2, default=str))
        else:
            print("Session not found")

async def search_sessions_cmd(args):
    """Search sessions by customer info"""
    analyzer = AsyncDataAnalyzer(args.db)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=args.days)
    
    sessions = await analyzer.search_sessions(
        customer_name=args.name,
        customer_phone=args.phone,
        date_from=start_date,
        date_to=end_date
    )
    
    print(f"\nFound {len(sessions)} matching sessions:")
    print(f"{'ID':<38} {'Date':<20} {'Customer':<20} {'Phone':<15} {'Booking':<20}")
    print("-" * 115)
    
    for session in sessions:
        session_id = session['id'][:36] + "..."
        start_time = session['start_time'][:19] if session['start_time'] else 'N/A'
        customer = session['customer_name'] or 'Unknown'
        phone = session['customer_phone'] or 'N/A'
        booking = session['booking_date_time'] or 'N/A'
        
        print(f"{session_id:<38} {start_time:<20} {customer:<20} {phone:<15} {booking:<20}")

async def stats_cmd(args):
    """Show statistics"""
    analyzer = AsyncDataAnalyzer(args.db)
    metrics = await analyzer.get_performance_metrics(args.days)
    interaction_analysis = await analyzer.get_customer_interaction_analysis()
    
    print(f"\n{'='*60}")
    print(f"PERFORMANCE METRICS ({args.days} days)")
    print(f"{'='*60}")
    
    print(f"Total Sessions: {metrics['total_sessions']}")
    print(f"Successful Bookings: {metrics['successful_bookings']}")
    print(f"Success Rate: {metrics['success_rate']:.1%}")
    print(f"Average Session Duration: {metrics['avg_session_duration']:.1f} seconds")
    
    if args.daily:
        print(f"\nDaily Breakdown:")
        print(f"{'Date':<12} {'Sessions':<10} {'Successful':<10} {'Success Rate':<12}")
        print("-" * 50)
        for date, stats in metrics['daily_breakdown'].items():
            rate = stats['successful'] / stats['sessions'] if stats['sessions'] > 0 else 0
            print(f"{date:<12} {stats['sessions']:<10} {stats['successful']:<10} {rate:.1%}")
    
    print(f"\n{'='*60}")
    print(f"INTERACTION ANALYSIS")
    print(f"{'='*60}")
    
    print(f"Message Distribution:")
    for role, count in interaction_analysis['role_distribution'].items():
        print(f"  {role}: {count}")
    
    print(f"\nAgent Usage:")
    for agent, count in interaction_analysis['agent_distribution'].items():
        print(f"  {agent}: {count}")
    
    session_analysis = interaction_analysis['session_analysis']
    print(f"\nSession Analysis:")
    print(f"  Success Rate: {session_analysis['success_rate']:.1%}")
    print(f"  Avg Duration (Successful): {session_analysis['avg_duration_successful']:.1f}s")
    print(f"  Avg Duration (Unsuccessful): {session_analysis['avg_duration_unsuccessful']:.1f}s")

async def export_cmd(args):
    """Export session data"""
    analyzer = AsyncDataAnalyzer(args.db)
    
    if args.format == 'txt':
        content = await analyzer.export_session_transcript(args.session_id)
    elif args.format == 'json':
        db_manager = AsyncDatabaseManager(args.db)
        session_data = await db_manager.get_session_data(args.session_id)
        content = json.dumps(session_data, indent=2, default=str)
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(content)
        print(f"Exported to {args.output}")
    else:
        print(content)

async def metrics_cmd(args):
    """Show metrics for a session"""
    analyzer = AsyncDataAnalyzer(args.db)
    metrics = await analyzer.get_metrics_for_session(args.session_id)
    
    if not metrics:
        print("No metrics found for this session")
        return
    
    print(f"\nMetrics for session {args.session_id}:")
    print(f"{'Type':<20} {'Name':<25} {'Value':<15} {'Unit':<10} {'Timestamp':<20}")
    print("-" * 95)
    
    for metric in metrics:
        print(f"{metric['metric_type']:<20} {metric['metric_name']:<25} {metric['value']:<15.3f} {metric['unit'] or 'N/A':<10} {str(metric['timestamp'])[:19]:<20}")

async def cleanup_cmd(args):
    """Clean up old data"""
    db_manager = AsyncDatabaseManager(args.db)
    cutoff_date = datetime.now() - timedelta(days=args.days)
    
    # Get sessions to be deleted
    analyzer = AsyncDataAnalyzer(args.db)
    sessions_to_delete = await analyzer.search_sessions(date_to=cutoff_date)
    
    if not sessions_to_delete:
        print("No old sessions found to clean up")
        return
    
    print(f"Found {len(sessions_to_delete)} sessions older than {args.days} days")
    
    if not args.confirm:
        print("Use --confirm to actually delete the data")
        return
    
    # Delete old sessions and related data
    async with db_manager.get_connection() as conn:
        for session in sessions_to_delete:
            session_id = session['id']
            
            # Delete related data
            await conn.execute("DELETE FROM transcripts WHERE session_id = ?", (session_id,))
            await conn.execute("DELETE FROM metrics WHERE session_id = ?", (session_id,))
            await conn.execute("DELETE FROM agent_transfers WHERE session_id = ?", (session_id,))
            await conn.execute("DELETE FROM user_data WHERE session_id = ?", (session_id,))
            await conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        
        await conn.commit()
    
    print(f"Deleted {len(sessions_to_delete)} old sessions")

if __name__ == "__main__":
    main()