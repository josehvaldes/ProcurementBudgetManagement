


from agents.approval_agent.tools.approval_status import ApprovalDecision


class ApprovalNotificationSystem:


    def send_alert(self, 
                   invoice:dict, 
                   vendor:dict, 
                   budget:dict,
                   decision: ApprovalDecision) -> None:
        print(f"Alert: Invoice {invoice['id']} from vendor {vendor['name']} exceeds the budget of {budget['amount']} for category {budget['category']}.\n")
        #TODO implement actual alert sending logic (e.g., email service integration)

