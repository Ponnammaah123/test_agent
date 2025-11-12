from fastapi import APIRouter, Depends, HTTPException, Header, status
from src.auth.authentication import authenticate_user
from src.utils.logger import get_logger

from src.config.settings import Config

from src.utils.exceptions import (
    JiraClientException,
    JiraAuthenticationException,
    JiraTicketNotFoundException,
    JiraPermissionException
)
from src.clients.jira_client import JiraClient
from src.models.FetchJiraTicketRequest import FetchJiraTicketRequest
from src.models.FetchJiraTicketResponse import FetchJiraTicketResponse


# Initialize config
config = Config()
config.validate()

logger = get_logger(__name__)

router = APIRouter()

#@router.post("/fetch-ticket", response_model=FetchJiraTicketResponse, dependencies=[Depends(authenticate_user)])
@router.post("/fetch-ticket", response_model=FetchJiraTicketResponse)
async def fetch_jira_ticket(request: FetchJiraTicketRequest
                            #, 
                            # token: str = Depends(extract_token)
                            ) -> FetchJiraTicketResponse:
    """
    Fetch Jira ticket details
    
    Args:
        request: FetchJiraTicketRequest containing ticket_id and optional flags
        
    Returns:
        FetchJiraTicketResponse with ticket information
        
    Raises:
        HTTPException: If ticket fetch fails
    """


    ticket_key = request.jira_ticket_id
    try:
        jira_client = JiraClient(config)
        ticket = jira_client.get_ticket(ticket_key)

        comments = []
        if request.include_comments:
            top_k_comments = request.latest_comment_count
            print(f"Fetching jira comments")
            try:
                comments_list = jira_client.get_comments(ticket_key, top_k_comments)
                comments = [att['body'] for att in comments_list]
                logger.info(f"Comments included in response")
            except JiraClientException as e:
                logger.info(
                    f"Failed to fetch comments: {str(e)}",
                    extra={'ticket_key': ticket_key}
                )
        
        attachments = []
        if request.include_attachments:
            logger.info(f"Fetching attachments")
            try:
                attachment_list = jira_client.get_attachments(ticket_key)
                attachments = attachment_list
                logger.info(
                    f"✓ Attachments fetched",
                    extra={
                        'count': len(attachments),
                        'total_size': sum(att.get('size', 0) for att in attachments)
                    }
                )
            except JiraClientException as e:
                logger.error(
                    f"Failed to fetch attachments: {str(e)}",
                    extra={'ticket_key': ticket_key}
                )
        
        # Prepare response
        response = FetchJiraTicketResponse(
            jira_id=ticket.key,
            jira_summary=ticket.summary,
            jira_status=ticket.status,
            jira_description=ticket.description or None,
            jira_assignee=ticket.assignee or None,
            comments=comments,
            attachments=attachments
        )
        return response

    except JiraAuthenticationException as e:
        raise HTTPException(
            status_code=401,
            detail="Jira authentication failed. Check credentials in configuration."
        )

    except JiraTicketNotFoundException as e:
        raise HTTPException(
            status_code=404,
            detail=f"Jira ticket '{ticket_key}' not found."
        )

    except JiraPermissionException as e:
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions to access this Jira ticket."
        )

    except JiraClientException as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to fetch Jira ticket: {str(e)}"
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred while fetching the Jira ticket."
        )