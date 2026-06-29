"""
modules/powershell_handler.py — JARVIS PowerShell Integration
==============================================================
Executes PowerShell commands and scripts on the local Windows system.
Provides a secure way to interact with the OS beyond standard file operations.
"""

import logging
import subprocess
logger = logging.getLogger(__name__)

class PowerShellHandler:
    """
    Handles generation and execution of PowerShell commands.
    Includes YOLO Classifier for advanced tool permissions.
    """
    
    def __init__(self, llm_engine=None):
        self.llm = llm_engine

    def classify_risk(self, command: str) -> dict:
        """
        YOLO Classifier: Classifies the risk of a command.
        Returns {"risk": "LOW|MEDIUM|HIGH", "explanation": "..."}
        """
        # Fast path for obvious safe commands to save API calls
        safe_prefixes = ("echo", "get-", "dir", "ls", "pwd", "write-output")
        if command.lower().strip().startswith(safe_prefixes) and "|" not in command:
            return {"risk": "LOW", "explanation": "This is a safe, read-only command."}
            
        if not self.llm:
            return {"risk": "HIGH", "explanation": "Risk classification unavailable. Proceed with caution."}
            
        prompt = f"""You are the YOLO Security Classifier. Evaluate the risk of executing this PowerShell command on the user's local Windows machine:
Command: `{command}`

Classify as LOW, MEDIUM, or HIGH risk. High risk implies destructive actions (delete, format, system changes, external execution).
Respond strictly in this format:
RISK: [LOW/MEDIUM/HIGH]
EXPLANATION: [One short sentence explaining why to the user]"""
        try:
            response = self.llm.generate([{"role": "user", "content": prompt}])
            risk_match = "HIGH"
            if "RISK: LOW" in response.upper(): risk_match = "LOW"
            elif "RISK: MEDIUM" in response.upper(): risk_match = "MEDIUM"
            
            exp_split = response.split("EXPLANATION:")
            explanation = exp_split[1].strip() if len(exp_split) > 1 else "Unknown risk factors."
            
            return {"risk": risk_match, "explanation": explanation}
        except Exception as e:
            logger.error(f"YOLO Classifier failed: {e}")
            return {"risk": "HIGH", "explanation": "Failed to classify risk due to an error."}

    def execute(self, command: str) -> str:
        """
        Execute a single PowerShell command or small script.
        
        Args:
            command (str): The PowerShell command string.
            
        Returns:
            str: Output of the command or an error message.
        """
        if not command:
            return "I need a command to execute, sir."

        logger.info(f"Executing PowerShell command: {command}")
        
        try:
            # We use -ExecutionPolicy Bypass to ensure scripts can run
            result = subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-Command", command],
                capture_output=True,
                text=True,
                check=False,
                timeout=30 # Safety timeout
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                if not output:
                    return "Command executed successfully with no output, sir."
                return f"Execution complete, sir. Output: {output[:500]}"
            else:
                error = result.stderr.strip()
                logger.error(f"PowerShell error: {error}")
                return f"I encountered an error executing the script, sir. Details: {error[:200]}"
                
        except subprocess.TimeoutExpired:
            logger.warning("PowerShell command timed out.")
            return "The script execution timed out, sir."
        except Exception as exc:
            logger.error(f"PowerShell execution failed: {exc}", exc_info=True)
            return f"I failed to execute the PowerShell command, sir. Error: {str(exc)}"

    def get_pc_info(self) -> str:
        """Example helper: Get advanced PC info via PowerShell."""
        cmd = "Get-ComputerInfo | Select-Object CsName, CsManufacturer, CsModel, OsName | ConvertTo-Json"
        return self.execute(cmd)
