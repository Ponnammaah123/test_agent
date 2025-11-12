from dotenv import load_dotenv
from datetime import datetime, timedelta
from dateutil import parser as date_parser

load_dotenv()

async def validate_existing_test_plan(input_params: dict
                                    #   , token: str
                                      ):
    """
    Check if test plan already exists in Jira attachments
    If found and recent (< 7 days), validate and use it instead of regenerating
    """
    try:
        logger = get_logger(__name__)
        logger.info("Checking for existing test plan...")
        
        attachments = input_params.get("attachments", [])
        
        logger.info(f"Processing {len(attachments)} total attachments")
        
        if not attachments:
            logger.info("No attachments found - will generate new test plan")
            return {
                "status": "success",
                "has_recent_test_plan": False
            }
        
        # Look for test plan attachments (PDF or Excel)
        test_plan_attachments = []
        for attachment in attachments:
            filename = attachment.get('filename', '')
            logger.info(f"Processing attachment: {filename}")
            
            if 'TestPlan' in filename and (
                filename.endswith('.pdf') or 
                filename.endswith('.xlsx')
            ):
                logger.info(f"Found test plan attachment: {filename}")
                test_plan_attachments.append(attachment)
            else:
                logger.info(f"Skipped non-test plan attachment: {filename}")
        
        logger.info(f"Found {len(test_plan_attachments)} test plan attachments")
        
        if not test_plan_attachments:
            logger.info("No test plan attachments found - will generate new one")
            return {
                "status": "success", 
                "has_recent_test_plan": False
            }
        
        # Log details of each test plan attachment
        for attachment in test_plan_attachments:
            filename = attachment.get('filename', '')
            created = attachment.get('created', '')
            logger.info(f"Test plan file: {filename}, Created: {created}")
        
        # Check if most recent test plan is recent enough (< 7 days)
        most_recent = max(test_plan_attachments, key=lambda a: a.get('created', ''))
        
        # Parse created date
        created_date = date_parser.parse(most_recent.get('created'))
        age_days = (datetime.now(created_date.tzinfo) - created_date).days
        
        logger.info(f"Most recent test plan: {most_recent.get('filename')}")
        logger.info(f"Created: {created_date.strftime('%Y-%m-%d %H:%M:%S')} ({age_days} days ago)")
        
        if age_days > 7:
            logger.info(f"Test plan is {age_days} days old (> 7 days) - will regenerate")
            return {
                "status": "success",
                "has_recent_test_plan": False
            }
        
        logger.info("Validation: Test plan is recent and valid - skipping regeneration")
        
        return {
            "status": "success",
            "has_recent_test_plan": True
        }
        
    except Exception as e:
        logger.error(f"Error validating test plan: {str(e)}")
        return {
            "status": "error",
            "message": f"Internal processing error: {str(e)}"
        }

def get_logger(name):
    """Simple logger implementation"""
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    return logging.getLogger(name)