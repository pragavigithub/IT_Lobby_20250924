#!/usr/bin/env python3
"""
SAP Job Worker - Background processor for SAP B1 integration jobs
This service processes jobs queued by the approval workflows to ensure
SAP operations persist even if users refresh pages during processing.
"""

import threading
import time
import logging
import json
from datetime import datetime, timedelta
from typing import Optional

from app import app, db
from models import SAPJob, GRPODocument, SerialItemTransfer
from sap_integration import SAPIntegration


class SAPJobWorker:
    """Background worker for processing SAP integration jobs"""
    
    def __init__(self, poll_interval: int = 10):
        """
        Initialize the SAP job worker
        
        Args:
            poll_interval: Seconds between polling for new jobs
        """
        self.poll_interval = poll_interval
        self.running = False
        self.thread = None
        self.sap = SAPIntegration()
        
    def start(self):
        """Start the background worker thread"""
        if self.running:
            logging.warning("SAP Job Worker is already running")
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.thread.start()
        logging.info("🚀 SAP Job Worker started")
        
    def stop(self):
        """Stop the background worker thread"""
        if not self.running:
            return
            
        self.running = False
        if self.thread:
            self.thread.join(timeout=30)
        logging.info("🛑 SAP Job Worker stopped")
        
    def _worker_loop(self):
        """Main worker loop that processes jobs"""
        with app.app_context():
            while self.running:
                try:
                    # Process pending jobs
                    self._process_pending_jobs()
                    
                    # Process retryable failed jobs
                    self._process_retry_jobs()
                    
                    # Sleep between polls
                    time.sleep(self.poll_interval)
                    
                except Exception as e:
                    logging.error(f"Error in SAP job worker loop: {str(e)}")
                    time.sleep(self.poll_interval)
                    
    def _process_pending_jobs(self):
        """Process all pending SAP jobs"""
        # Get pending jobs ordered by creation time
        pending_jobs = SAPJob.query.filter_by(status='pending').order_by(SAPJob.created_at).all()
        
        for job in pending_jobs:
            try:
                self._process_job(job)
            except Exception as e:
                logging.error(f"Error processing job {job.id}: {str(e)}")
                self._mark_job_failed(job, str(e))
                
    def _process_retry_jobs(self):
        """Process jobs that are ready for retry"""
        retry_time = datetime.utcnow()
        retry_jobs = SAPJob.query.filter(
            SAPJob.status == 'retrying',
            SAPJob.next_retry_at <= retry_time
        ).order_by(SAPJob.created_at).all()
        
        for job in retry_jobs:
            try:
                self._process_job(job)
            except Exception as e:
                logging.error(f"Error retrying job {job.id}: {str(e)}")
                self._handle_job_retry(job, str(e))
                
    def _process_job(self, job: SAPJob):
        """Process a single SAP job"""
        logging.info(f"🔄 Processing SAP job {job.id}: {job.job_type} for {job.document_type}#{job.document_id}")
        
        # Mark job as processing
        job.status = 'processing'
        job.started_at = datetime.utcnow()
        db.session.commit()
        
        try:
            if job.job_type == 'grpo_post':
                self._process_grpo_job(job)
            elif job.job_type == 'serial_transfer':
                self._process_serial_transfer_job(job)
            else:
                raise ValueError(f"Unknown job type: {job.job_type}")
                
        except Exception as e:
            # Handle job failure
            self._handle_job_retry(job, str(e))
            raise
            
    def _process_grpo_job(self, job: SAPJob):
        """Process a GRPO posting job"""
        payload = json.loads(job.payload)
        grpo_id = payload['grpo_id']
        
        # Get the GRPO document
        grpo = GRPODocument.query.get(grpo_id)
        if not grpo:
            raise ValueError(f"GRPO document {grpo_id} not found")
            
        logging.info(f"📦 Posting GRPO {grpo_id} to SAP B1...")
        
        # Post to SAP B1
        sap_result = self.sap.post_grpo_to_sap(grpo)
        
        if sap_result.get('success'):
            # Success - update both job and document
            sap_doc_number = sap_result.get('sap_document_number')
            
            grpo.sap_document_number = sap_doc_number
            grpo.status = 'posted'
            grpo.updated_at = datetime.utcnow()
            
            job.status = 'completed'
            job.completed_at = datetime.utcnow()
            job.sap_document_number = sap_doc_number
            job.result = json.dumps(sap_result)
            
            db.session.commit()
            
            logging.info(f"✅ GRPO {grpo_id} posted to SAP B1 as {sap_doc_number}")
            
        else:
            # SAP posting failed
            error_msg = sap_result.get('error', 'Unknown SAP error')
            raise Exception(f"SAP posting failed: {error_msg}")
            
    def _process_serial_transfer_job(self, job: SAPJob):
        """Process a Serial Item Transfer posting job"""
        payload = json.loads(job.payload)
        transfer_id = payload['transfer_id']
        
        # Get the transfer document
        transfer = SerialItemTransfer.query.get(transfer_id)
        if not transfer:
            raise ValueError(f"Serial Item Transfer {transfer_id} not found")
            
        logging.info(f"📦 Posting Serial Item Transfer {transfer_id} to SAP B1...")
        
        # Post to SAP B1
        sap_result = self.sap.create_serial_item_stock_transfer(transfer)
        
        if sap_result.get('success'):
            # Success - update both job and document
            sap_doc_number = sap_result.get('document_number')
            
            transfer.sap_document_number = sap_doc_number
            transfer.status = 'posted'
            transfer.updated_at = datetime.utcnow()
            
            job.status = 'completed'
            job.completed_at = datetime.utcnow()
            job.sap_document_number = sap_doc_number
            job.result = json.dumps(sap_result)
            
            db.session.commit()
            
            logging.info(f"✅ Serial Item Transfer {transfer_id} posted to SAP B1 as {sap_doc_number}")
            
        else:
            # SAP posting failed
            error_msg = sap_result.get('error', 'Unknown SAP error')
            raise Exception(f"SAP posting failed: {error_msg}")
            
    def _handle_job_retry(self, job: SAPJob, error_message: str):
        """Handle job retry logic"""
        job.retry_count += 1
        job.error_message = error_message
        
        if job.retry_count >= job.max_retries:
            # Max retries reached - mark as failed
            self._mark_job_failed(job, error_message)
        else:
            # Schedule for retry with exponential backoff
            retry_delay = min(300, 30 * (2 ** (job.retry_count - 1)))  # 30s, 60s, 120s, 240s, max 300s
            job.status = 'retrying'
            job.next_retry_at = datetime.utcnow() + timedelta(seconds=retry_delay)
            
            logging.warning(f"⚠️ Job {job.id} failed (attempt {job.retry_count}/{job.max_retries}), retrying in {retry_delay}s: {error_message}")
            
        db.session.commit()
        
    def _mark_job_failed(self, job: SAPJob, error_message: str):
        """Mark job as permanently failed"""
        job.status = 'failed'
        job.completed_at = datetime.utcnow()
        job.error_message = error_message
        
        # Update document status to indicate sync failure
        if job.document_type == 'grpo':
            grpo = GRPODocument.query.get(job.document_id)
            if grpo:
                grpo.status = 'qc_approved'  # Keep as approved but not posted
                
        elif job.document_type == 'serial_item_transfer':
            transfer = SerialItemTransfer.query.get(job.document_id)
            if transfer:
                transfer.status = 'qc_approved'  # Keep as approved but not posted
                
        db.session.commit()
        
        logging.error(f"❌ Job {job.id} permanently failed after {job.retry_count} attempts: {error_message}")


# Global worker instance
sap_worker: Optional[SAPJobWorker] = None


def start_sap_worker():
    """Start the global SAP job worker"""
    global sap_worker
    
    if sap_worker is None:
        sap_worker = SAPJobWorker(poll_interval=10)
        sap_worker.start()
    

def stop_sap_worker():
    """Stop the global SAP job worker"""
    global sap_worker
    
    if sap_worker:
        sap_worker.stop()
        sap_worker = None


if __name__ == "__main__":
    # For testing - run the worker directly
    import signal
    import sys
    
    def signal_handler(sig, frame):
        print("Stopping SAP Job Worker...")
        stop_sap_worker()
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    start_sap_worker()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_sap_worker()