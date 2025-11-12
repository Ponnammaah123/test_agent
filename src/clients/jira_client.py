from jira import JIRA
from jira.exceptions import JIRAError
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from dateutil import parser as date_parser

from src.config.settings import Config
from src.models.jira_models import JiraTicket
from src.models.test_plan_models import TestPlan
from src.utils.logger import get_logger
from src.utils.exceptions import JiraClientException

logger = get_logger(__name__)

class JiraClient:
    """Client for Jira API integration"""
    
    def __init__(self, config: Config):
        """
        Initialize Jira client
        
        Args:
            config: Application configuration
        """
        self.config = config
        try:
            self.client = JIRA(
                server=config.jira.server,
                basic_auth=(config.jira.email, config.jira.api_token)
            )
            logger.info(f"Connected to Jira: {config.jira.server}")
        except JIRAError as e:
            raise JiraClientException(f"Failed to connect to Jira: {str(e)}")
    
    def get_ticket(self, ticket_key: str) -> JiraTicket:
        """
        Fetch complete ticket details from Jira
        
        Args:
            ticket_key: Jira ticket key (e.g., PROJ-456)
            
        Returns:
            JiraTicket object with all details
            
        Raises:
            JiraClientException: If ticket cannot be fetched
        """
        logger.info(f"Fetching Jira ticket: {ticket_key}")
        
        try:
            issue = self.client.issue(
                ticket_key,
                expand='changelog,renderedFields'
            )
            
            # Extract acceptance criteria
            acceptance_criteria = self._extract_acceptance_criteria(issue)
            
            # Get linked issues
            linked_issues = []
            if hasattr(issue.fields, 'issuelinks'):
                for link in issue.fields.issuelinks:
                    if hasattr(link, 'outwardIssue'):
                        linked_issues.append(link.outwardIssue.key)
                    elif hasattr(link, 'inwardIssue'):
                        linked_issues.append(link.inwardIssue.key)
            
            # Extract components
            components = []
            if hasattr(issue.fields, 'components') and issue.fields.components:
                components = [c.name for c in issue.fields.components]
            
            # Extract labels
            labels = []
            if hasattr(issue.fields, 'labels') and issue.fields.labels:
                labels = list(issue.fields.labels)

            # Extract hierarchical relationships
            parent_key = None
            epic_key = None
            epic_name = None
            subtasks = []
            is_subtask = False

            # Check if this is a subtask
            if hasattr(issue.fields, 'parent'):
                parent_key = issue.fields.parent.key
                is_subtask = True
                logger.debug(f"Ticket {ticket_key} is a subtask of {parent_key}")

            # Get epic link (custom field, varies by Jira instance)
            if hasattr(issue.fields, 'customfield_10014') and issue.fields.customfield_10014:
                epic_key = issue.fields.customfield_10014
                logger.debug(f"Ticket {ticket_key} linked to epic {epic_key}")
            elif hasattr(issue.fields, 'customfield_10008') and issue.fields.customfield_10008:
                epic_key = issue.fields.customfield_10008

            # Get epic name (if this ticket IS an epic)
            if hasattr(issue.fields, 'customfield_10011') and issue.fields.customfield_10011:
                epic_name = issue.fields.customfield_10011
            elif epic_key:
                try:
                    epic_issue = self.client.issue(epic_key)
                    if hasattr(epic_issue.fields, 'customfield_10011'):
                        epic_name = epic_issue.fields.customfield_10011
                    else:
                        epic_name = epic_issue.fields.summary
                except Exception as e:
                    logger.warning(f"Could not fetch epic name for {epic_key}: {str(e)}")
                    epic_name = epic_key

            # Get subtasks
            if hasattr(issue.fields, 'subtasks') and issue.fields.subtasks:
                subtasks = [st.key for st in issue.fields.subtasks]
                logger.debug(f"Ticket {ticket_key} has {len(subtasks)} subtasks")

            # Parse dates safely using python-dateutil
            created_date = None
            updated_date = None

            try:
                if hasattr(issue.fields, 'created') and issue.fields.created:
                    created_date = date_parser.parse(issue.fields.created)
            except Exception as e:
                logger.warning(f"Could not parse created date: {str(e)}")

            try:
                if hasattr(issue.fields, 'updated') and issue.fields.updated:
                    updated_date = date_parser.parse(issue.fields.updated)
            except Exception as e:
                logger.warning(f"Could not parse updated date: {str(e)}")

            ticket = JiraTicket(
                key=issue.key,
                summary=issue.fields.summary,
                description=issue.fields.description or "",
                story_type=issue.fields.issuetype.name,
                acceptance_criteria=acceptance_criteria,
                components=components,
                linked_issues=linked_issues,
                assignee=issue.fields.assignee.displayName if issue.fields.assignee else "",
                status=issue.fields.status.name,
                priority=issue.fields.priority.name if hasattr(issue.fields, 'priority') and issue.fields.priority else "Medium",
                reporter=issue.fields.reporter.displayName if issue.fields.reporter else "",
                created=created_date,
                updated=updated_date,
                labels=labels,
                parent_key=parent_key,
                epic_key=epic_key,
                epic_name=epic_name,
                subtasks=subtasks,
                is_subtask=is_subtask
            )
            
            logger.info(f"Successfully fetched ticket: {ticket_key}")
            return ticket

        except JIRAError as e:
            raise JiraClientException(f"Failed to fetch ticket {ticket_key}: {str(e)}")

    def get_attachments(self, ticket_key: str) -> List[dict]:
        """
        Get all attachments from a Jira ticket

        Args:
            ticket_key: Jira ticket key (e.g., PROJ-456)

        Returns:
            List of attachment dictionaries with keys: filename, content (URL), id, size, created

        Raises:
            JiraClientException: If ticket cannot be fetched
        """
        logger.info(f"Fetching attachments for Jira ticket: {ticket_key}")

        try:
            issue = self.client.issue(ticket_key)

            attachments = []
            if hasattr(issue.fields, 'attachment') and issue.fields.attachment:
                for attachment in issue.fields.attachment:
                    attachments.append({
                        'id': attachment.id,
                        'filename': attachment.filename,
                        'content': attachment.content,  # Download URL
                        'size': attachment.size,
                        'created': attachment.created,
                        'mimeType': attachment.mimeType if hasattr(attachment, 'mimeType') else None
                    })

            logger.info(f"Found {len(attachments)} attachments for {ticket_key}")
            return attachments

        except JIRAError as e:
            raise JiraClientException(f"Failed to fetch attachments for {ticket_key}: {str(e)}")

    def get_comments(self, ticket_key: str, top_n: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetch comments from a Jira ticket
        
        Args:
            ticket_key: Jira ticket key (e.g., PROJ-456)
            top_n: Number of most recent comments to fetch. If None, fetches all.
                   If negative, fetches the oldest comments.
                   If 0, returns empty list.
        
        Returns:
            List of comment dictionaries with keys:
            - id: Comment ID
            - author: Author display name
            - author_email: Author email (if available)
            - body: Comment text
            - created: Comment creation datetime
            - updated: Comment update datetime (if edited)
            - edited: Boolean indicating if comment was edited
            - is_public: Boolean indicating if comment is public
        
        Raises:
            JiraClientException: If comments cannot be fetched
        
        Examples:
            # Get all comments
            comments = client.get_comments("PROJ-123")
            
            # Get top 5 most recent comments
            recent_comments = client.get_comments("PROJ-123", top_n=5)
            
            # Get 3 oldest comments
            oldest_comments = client.get_comments("PROJ-123", top_n=-3)
        """
        logger.info(f"Fetching comments for ticket {ticket_key}, top_n={top_n}")
        
        try:
            # Handle edge case
            if top_n == 0:
                logger.info(f"top_n=0, returning empty comment list for {ticket_key}")
                return []
            
            # Fetch issue with comments
            issue = self.client.issue(ticket_key, expand='changelog')
            
            # Get all comments
            all_comments = []
            if hasattr(issue.fields, 'comment') and issue.fields.comment:
                comments_obj = issue.fields.comment
                
                if hasattr(comments_obj, 'comments'):
                    # comments_obj is a Response object with comments attribute
                    for comment in comments_obj.comments:
                        formatted_comment = self._format_comment(comment)
                        all_comments.append(formatted_comment)
                else:
                    # Handle if it's already a list
                    for comment in (comments_obj if isinstance(comments_obj, list) else [comments_obj]):
                        formatted_comment = self._format_comment(comment)
                        all_comments.append(formatted_comment)
            
            logger.info(f"Found {len(all_comments)} total comments for {ticket_key}")
            
            # Sort by creation date (most recent first)
            all_comments.sort(
                key=lambda c: c['created'] if c['created'] else datetime.min,
                reverse=True
            )
            
            # Handle top_n parameter
            if top_n is None:
                # Return all comments
                result = all_comments
            elif top_n > 0:
                # Return most recent N comments
                result = all_comments[:top_n]
            else:
                # Return oldest N comments (reverse order)
                result = all_comments[top_n:][::-1]  # Reverse to get oldest first
            
            logger.info(f"Returning {len(result)} comments for {ticket_key}")
            return result
        
        except JIRAError as e:
            error_msg = f"Failed to fetch comments for {ticket_key}: {str(e)}"
            logger.error(error_msg)
            raise JiraClientException(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error fetching comments for {ticket_key}: {str(e)}"
            logger.error(error_msg)
            raise JiraClientException(error_msg)

    def _format_comment(self, comment) -> Dict[str, Any]:
        """
        Format a Jira comment into a dictionary with useful information
        
        Args:
            comment: Jira comment object
        
        Returns:
            Dictionary with comment information
        """
        try:
            # Extract author information
            author_name = ""
            author_email = ""
            
            if hasattr(comment, 'author'):
                if hasattr(comment.author, 'displayName'):
                    author_name = comment.author.displayName
                if hasattr(comment.author, 'emailAddress'):
                    author_email = comment.author.emailAddress
            
            # Extract timestamps
            created_date = None
            updated_date = None
            
            try:
                if hasattr(comment, 'created') and comment.created:
                    created_date = date_parser.parse(comment.created)
            except Exception as e:
                logger.warning(f"Could not parse comment created date: {str(e)}")
            
            try:
                if hasattr(comment, 'updated') and comment.updated:
                    updated_date = date_parser.parse(comment.updated)
            except Exception as e:
                logger.warning(f"Could not parse comment updated date: {str(e)}")
            
            # Check if comment was edited
            is_edited = updated_date and created_date and (updated_date > created_date)
            
            # Extract comment body
            comment_body = ""
            if hasattr(comment, 'body'):
                comment_body = comment.body or ""
            
            # Check if comment is public
            is_public = True  # Default to public
            if hasattr(comment, 'visibility'):
                is_public = not hasattr(comment.visibility, 'type') or comment.visibility.type == 'public'
            
            return {
                'id': comment.id if hasattr(comment, 'id') else None,
                'author': author_name,
                'author_email': author_email,
                'body': comment_body,
                'created': created_date,
                'updated': updated_date,
                'edited': is_edited,
                'is_public': is_public
            }
        
        except Exception as e:
            logger.warning(f"Error formatting comment: {str(e)}")
            # Return minimal comment structure on error
            return {
                'id': None,
                'author': 'Unknown',
                'author_email': '',
                'body': 'Error formatting comment',
                'created': None,
                'updated': None,
                'edited': False,
                'is_public': True
            }

    def get_recent_comments(self, ticket_key: str, days: int = 7) -> List[Dict[str, Any]]:
        """
        Fetch comments from the last N days
        
        Args:
            ticket_key: Jira ticket key (e.g., PROJ-456)
            days: Number of days to look back (default: 7)
        
        Returns:
            List of comment dictionaries from the last N days, sorted by date (newest first)
        
        Raises:
            JiraClientException: If comments cannot be fetched
        
        Example:
            # Get comments from last 3 days
            recent = client.get_recent_comments("PROJ-123", days=3)
        """
        logger.info(f"Fetching comments from last {days} days for {ticket_key}")
        
        try:
            # Get all comments
            all_comments = self.get_comments(ticket_key, top_n=None)
            
            # Filter by date
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            recent_comments = [
                c for c in all_comments 
                if c['created'] and c['created'] > cutoff_date
            ]
            
            logger.info(f"Found {len(recent_comments)} comments from last {days} days for {ticket_key}")
            return recent_comments
        
        except Exception as e:
            error_msg = f"Failed to fetch recent comments for {ticket_key}: {str(e)}"
            logger.error(error_msg)
            raise JiraClientException(error_msg)

    def _extract_acceptance_criteria(self, issue) -> List[str]:
        """Extract acceptance criteria from ticket description"""
        criteria = []
        
        if not issue.fields.description:
            return criteria

        for line in issue.fields.description.split('\n'):
            if line.strip():
                # Check for common acceptance criteria markers
                prefixes = ['given', 'when', 'then', 'and', 'but', 'scenario', 'as a', 'i want', 'so that', 'acceptance:']
                
                cleaned = line.strip()
                if cleaned.lower().startswith('acceptance') or cleaned.lower().startswith('ac:'):
                    cleaned = cleaned.split(':', 1)[1].strip() if ':' in cleaned else cleaned
                
                # Remove common bullet point markers
                for prefix in ['*', '-', '•', '►', '◆']:
                    if cleaned.startswith(prefix):
                        cleaned = cleaned[1:].strip()
                        break
                
                # Remove numbering like "1.", "2."
                if cleaned and cleaned[0].isdigit() and '.' in cleaned[:3]:
                    cleaned = cleaned.split('.', 1)[1].strip()
                
                if cleaned and len(cleaned) > 5:  # Ignore very short lines
                    criteria.append(cleaned)
        
        logger.debug(f"Extracted {len(criteria)} acceptance criteria")
        return criteria
    
    def attach_test_plan(self, ticket_key: str, test_plan: TestPlan) -> bool:
        """Attach test plan document to Jira ticket as comment"""
        logger.info(f"Attaching test plan to {ticket_key}")
        
        try:
            issue = self.client.issue(ticket_key)
            comment = self._format_test_plan_comment(test_plan)
            self.client.add_comment(issue, comment)
            logger.info(f"Successfully attached test plan to {ticket_key}")
            return True
        except JIRAError as e:
            raise JiraClientException(f"Failed to attach test plan to {ticket_key}: {str(e)}")

    def add_comment(self, ticket_key: str, comment: str) -> bool:
        """Add a comment to Jira ticket"""
        try:
            issue = self.client.issue(ticket_key)
            self.client.add_comment(issue, comment)
            logger.info(f"Added comment to {ticket_key}")
            return True
        except JIRAError as e:
            logger.error(f"Failed to add comment to {ticket_key}: {str(e)}")
            return False

    def _format_test_plan_comment(self, plan: TestPlan) -> str:
        """Format test plan as Jira-formatted comment"""
        env_info = ""
        if plan.environment_config:
            env_info = f"""
                h4. Test Environment Configuration
                * Application URL: {plan.environment_config.test_environment_url}
                * API Base URL: {plan.environment_config.api_base_url}
                {f"* Admin URL: {plan.environment_config.admin_url}" if plan.environment_config.admin_url else ""}
                """
        
        scenarios_by_type = {}
        for scenario in plan.test_scenarios:
            test_type = scenario.get('test_type', 'Unknown')
            scenarios_by_type[test_type] = scenarios_by_type.get(test_type, 0) + 1
        
        scenarios_summary = "\n".join([
            f"* {test_type}: {count} scenarios"
            for test_type, count in scenarios_by_type.items()
        ])
        
        traceability = "\n".join([
            f"* {ac}: {', '.join(scenarios)}"
            for ac, scenarios in plan.traceability_matrix.items()
        ])
        
        return f"""
            h3. 🤖 QE Agent Test Plan Generated

            h4. Summary
            * *Strategy:* {plan.strategy}
            * *Approach:* {plan.test_approach}
            * *Confidence Score:* {plan.confidence_score:.0f}/100

            h4. Testable Components
            {chr(10).join(['* ' + comp for comp in plan.testable_components])}

            h4. Test Scenarios ({len(plan.test_scenarios)} total)
            {scenarios_summary}

            h4. Coverage Targets
            {chr(10).join([f'* {k}: {v}' for k, v in plan.coverage_targets.items()])}

            h4. Traceability Matrix
            {traceability}
            {env_info}
            ----
            _Generated by QE Agent | Full test implementation will be available in repository_
                    """.strip()
    
    def update_ticket_status(self, ticket_key: str, status: str) -> bool:
        """Update ticket status"""
        try:
            issue = self.client.issue(ticket_key)
            transitions = self.client.transitions(issue)
            
            for transition in transitions:
                if transition['name'].lower() == status.lower():
                    self.client.transition_issue(issue, transition['id'])
                    logger.info(f"Updated {ticket_key} status to {status}")
                    return True
            
            logger.warning(f"Status '{status}' not available for {ticket_key}")
            return False
        except JIRAError as e:
            logger.error(f"Failed to update status: {str(e)}")
            return False
    
    def add_label(self, ticket_key: str, label: str) -> bool:
        """Add label to ticket"""
        try:
            issue = self.client.issue(ticket_key)
            current_labels = list(issue.fields.labels)

            if label not in current_labels:
                current_labels.append(label)
                issue.update(fields={'labels': current_labels})
                logger.info(f"Added label '{label}' to {ticket_key}")

            return True
        except JIRAError as e:
            logger.error(f"Failed to add label: {str(e)}")
            return False

    def attach_files(self, ticket_key: str, file_paths: List[str]) -> bool:
        """Attach files to Jira ticket"""
        logger.info(f"Attaching {len(file_paths)} files to {ticket_key}")

        try:
            issue = self.client.issue(ticket_key)

            for file_path in file_paths:
                with open(file_path, 'rb') as file:
                    self.client.add_attachment(
                        issue=issue,
                        attachment=file,
                        filename=file_path.split('/')[-1]
                    )
                    logger.info(f"  ✓ Attached: {file_path.split('/')[-1]}")

            logger.info(f"Successfully attached {len(file_paths)} files to {ticket_key}")
            return True

        except JIRAError as e:
            raise JiraClientException(f"Failed to attach files to {ticket_key}: {str(e)}")
        except FileNotFoundError as e:
            raise JiraClientException(f"File not found: {str(e)}")