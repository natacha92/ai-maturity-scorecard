<<<<<<< HEAD
# Compatibilité : re-exporte depuis engine.rules
from engine.rules import parse_rule

__all__ = ["parse_rule"]
=======
from typing import Optional, Dict, Any

def parse_rule(rule: Optional[str], responses: Dict[str, Dict[str, Any]]) -> bool:
    if not rule or rule == "always":
        return True

    if rule.startswith("only_if(") and rule.endswith(")"):
        expression = rule[len("only_if("):-1].strip()

        for operator in [">=", "<=", "==", ">", "<"]:
            if operator in expression:
                left, right = expression.split(operator, 1)
                left = left.strip()
                right = right.strip()

                response = responses.get(left)
                if not response:
                    return False

                if (right.startswith("'") and right.endswith("'")) or (
                    right.startswith('"') and right.endswith('"')
                ):
                    expected_text = right[1:-1]
                    current_text = response.get("selected_choice") or response.get("value")
                    if current_text is None:
                        return False
                    return operator == "==" and str(current_text) == expected_text

                value = response.get("score")
                if value is None:
                    return False

                try:
                    current_num = float(value)
                    expected_num = float(right)
                except ValueError:
                    return False

                if operator == ">=":
                    return current_num >= expected_num
                if operator == "<=":
                    return current_num <= expected_num
                if operator == "==":
                    return current_num == expected_num
                if operator == ">":
                    return current_num > expected_num
                if operator == "<":
                    return current_num < expected_num

    return True
>>>>>>> 4d21a07f1eb59284ad0d7a8d4c38ce706e8e8fdd
