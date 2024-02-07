"""
Validation functions for checking that data input fulfills the module requirements.
"""
from typing import Tuple, Union, List, Dict, Any


class ValidationError(Exception):
    """
    Base class for validation errors.
    """
    pass


def _is_same_data_type(data_type: str, value: Any) -> bool:
    """
    Check if the data type of a value matches the given one.

    :param data_type: The data type.
    :param value: The value.

    :returns: True if it is the same type, otherwise false.
    """
    data_types: List[str] = data_type.split("/")
    correct_type: List[bool] = []

    for data_type in data_types:
        if data_type in ["strs", "bools", "ints", "floats", "numbers"]:
            if type(value) == list:
                correct = True
                for item in value:
                    # Check if every value is of the given type.
                    if data_type == "numbers":
                        if type(item).__name__ != "int" and type(item).__name__ != "float":
                            correct = False
                            break
                    elif type(item).__name__ != data_type[:-1]:
                        correct = False
                        break
                correct_type.append(correct)
            else:
                correct_type.append(False)
        elif data_type == "list":
            correct_type.append(bool(type(value) == list))
        elif data_type in ["str", "bool", "int", "float"]:
            correct_type.append(bool(type(value).__name__ == data_type))
        elif data_type == "number":
            correct_type.append(bool(type(value).__name__ == "int" or type(value).__name__ == "float"))
        else:  # Unknown data type.
            raise Exception(f"Unknown data type '{data_type}'.")

    return True in correct_type


def _evaluate_expression(expression: str, data: dict) -> Tuple[bool, List[str]]:
    """
    Evaluates an expression, which is part of a requirement.

    :param expression: The single expression to be evaluated.
    :param data: The data object.

    :returns: Is the expression valid and a list of validation messages.
    """
    messages: List[str] = []
    valid: bool = True

    try:
        variables = expression.split(" ")
        if variables[0] == "key":
            if variables[2] == "with" if len(variables) >= 3 else False:  # Check if name is followed by 'with'.
                for key, value in data.items():  # Get every key/value pair of the data object.
                    if variables[1][0] == '!':  # Check every key/value data type expect the given key.
                        if variables[1].replace('!', '', 1) != key:
                            if not _is_same_data_type(data_type=variables[3], value=value):
                                valid = False
                                messages.append(f"The value '{value}' of key '{key}' is not of type {variables[3]} "
                                                f"but was {type(value).__name__}.")
                    elif variables[1] == '*':  # Check every key/value to be of the correct data type.
                        if not _is_same_data_type(data_type=variables[3], value=value):
                            valid = False
                            messages.append(f"The value '{value}' of key '{key}' is not of type {variables[3]} "
                                            f"but was {type(value).__name__}.")
                    else:  # Check only values of the given key to be of the correct data type.
                        if variables[1] == key:
                            if not _is_same_data_type(data_type=variables[3], value=value):
                                valid = False
                                messages.append(f"The value '{value}' of key '{key}' is not of type {variables[3]} "
                                                f"but was {type(value).__name__}.")
            # Always check if the key exists or not.
            if variables[1][0] == '!':  # Key should not be in dict.
                if variables[2] == "with":
                    # If followed by with, the '!' has the meaning, that every key except this one.
                    # This means, we do not check here, if the key exists.
                    pass
                elif variables[1].replace('!', '', 1) in data.keys():
                    valid = False
                    messages.append(f"The key '{variables[1].replace('!', '', 1)}' "
                                    f"should not be in the data object but was.")
            elif variables[1] == '*':  # There should be at least one key.
                if not data:
                    valid = False
                    messages.append("There should be at least one key in the data object.")
            else:  # Given key should be in dict.
                if variables[1] not in data.keys():
                    valid = False
                    messages.append(f"The key '{variables[1]}' should be in the data object but wasn't.")

        elif variables[0] == "keys":  # Check the length of the data object.
            valid_input = True
            if variables[1] not in ['==', '!=', '>=', '<=', '<', '>']:
                raise Exception(f"'{variables[1]}' is an unknown operator for checking the length of the data object.")
            if not variables[2].isdigit():
                raise Exception(f"'{variables[2]}' is not a valid number for checking the length of the data object.")
            if valid_input:
                valid = eval(str(len(data.items())) + variables[1] + variables[2], {})
            if not valid:
                messages.append(f"The length of the data object should be '{variables[1]} {variables[2]}' "
                                f"but was '{len(data.items())}'.")

        elif variables[0] == "length":
            # Example: (length * equal), (length * == 2), or (length !event equal).
            if variables[1] == '*' or variables[1][0] == '!':
                key_not_to_be_checked = None
                if variables[1][0] == '!':
                    key_not_to_be_checked = variables[1].replace('!', '', 1)
                # Check the length off all elements of the data object to be 'operator number' or 'equal'.
                if variables[2] in ['==', '!=', '>=', '<=', '<', '>']:
                    if not variables[3].isdigit():
                        raise Exception(f"'{variables[3]}' is not a valid number for checking the length of a list.")
                    else:
                        same_length = True
                        for key, value in data.items():  # Get every key/value pair of the data object.
                            if key == key_not_to_be_checked:
                                continue
                            if type(value) == list:
                                if not eval(str(len(value)) + variables[2] + variables[3], {}):
                                    same_length = False
                                    break
                            else:
                                same_length = False
                                break
                        if not same_length:
                            valid = False
                            messages.append(f"All values should be lists of length '{variables[2]} {variables[3]}'.")
                elif variables[2] == 'equal':  # All values should be lists of the same length.
                    same_length = True
                    list_of_lists = []
                    for key, value in data.items():  # Get every key/value pair of the data object.
                        if key == key_not_to_be_checked:
                            continue
                        if type(value) == list:
                            list_of_lists.append(value)
                        else:
                            same_length = False
                            break
                    if not same_length:
                        valid = False
                        messages.append("All values should be lists of the same length.")
                    else:
                        # Check if length of all lists are the same.
                        if not len(set(map(len, list_of_lists))) <= 1:
                            valid = False
                            messages.append("All values should be lists of the same length.")
                else:
                    raise Exception(f"'{variables[2]}' is an unknown operator for checking the length of a list.")

            # Should be a key of the data object. Example: (length test1 == test2) or (length test1 == 2).
            elif variables[1] in data.keys():
                if type(data.get(variables[1], None)) is list:
                    if variables[3].isdigit():  # Check if to compare with a number or key.
                        if variables[2] in ['==', '!=', '>=', '<=', '<', '>']:
                            valid = eval(str(len(data.get(variables[1]))) + variables[2] + variables[3], {})
                            if not valid:
                                messages.append(f"The length of the list from key '{variables[1]}' "
                                                f"should be '{variables[2]} {variables[3]}' but was "
                                                f"'{len(data.get(variables[1]))}'.")
                        else:
                            raise Exception(f"'{variables[2]}' is an unknown operator for comparing "
                                            f"the length of lists.")
                    else:  # Compare with another list.
                        if variables[3] in data.keys():
                            if type(data.get(variables[3], None)) is list:
                                if variables[2] in ['==', '!=', '>=', '<=', '<', '>']:
                                    valid = eval(str(len(data.get(variables[1]))) + variables[2] + str(
                                        len(data.get(variables[3]))), {})
                                    if not valid:
                                        messages.append(
                                            f"The length of the list from key '{variables[1]}' should be "
                                            f"'{variables[2]} {len(data.get(variables[3]))}' but was "
                                            f"'{len(data.get(variables[1]))}'.")
                                else:
                                    raise Exception(f"'{variables[1]}' is an unknown operator for comparing "
                                                    f"the length of lists.")
                            else:
                                valid = False
                                messages.append(f"The value of key '{variables[3]}' should be a list.")
                        else:
                            valid = False
                            messages.append(f"The key '{variables[3]}' was not found in the data object.")
                else:
                    valid = False
                    messages.append(f"The value of key '{variables[1]}' should be a list.")
            else:
                valid = False
                messages.append(f"The key '{variables[1]}' was not found in the data object.")

        elif variables[0] == "value":
            # Should be a key of the data object. Example: (value test1 == 1).
            if variables[1] in data.keys():
                if variables[2] in ['==', '!=', '>=', '<=', '<', '>']:
                    if isinstance(data.get(variables[1]), str):
                        variable_1 = '"' + str(data.get(variables[1])) + '"'
                    else:
                        variable_1 = str(data.get(variables[1]))

                    valid = eval(variable_1 + variables[2] + variables[3], {variables[3]: variables[3]})
                    if not valid:
                        messages.append(f"The value of the key '{variables[1]}' "
                                        f"should be '{variables[2]} {variables[3]}' but was "
                                        f"'{data.get(variables[1])}'.")
                else:
                    raise Exception(f"'{variables[2]}' is an unknown operator for comparing values.")
            else:
                valid = False
                messages.append(f"The key '{variables[1]}' was not found in the data object.")
        else:
            raise Exception(f"Unknown expression: '{expression}'.")

        # Make sure that valid is a boolean.
        if type(valid) is not bool:
            raise Exception(f"Evaluation of expression '{expression}' did not return a boolean.")
    except Exception as e:
        raise Exception(f"Could not evaluate expression '{expression}': " + str(e))

    return valid, messages


def _evaluate_requirement(requirement: str, data: dict) -> Tuple[bool, List[str]]:
    """
    Evaluate the single requirements.

    :param requirement: The requirement to be evaluated.
    :param data: The data object.

    :returns: Is the requirement valid and a list of validation messages.
    """
    messages: List[str] = []

    if not requirement[0] == "(" or not requirement[-1] == ")":
        raise Exception(f"Could not evaluate requirement '{requirement}': "
                        f"A requirement has to start with '(' and end with ')'.")

    # Extract the single expressions from the string. An expression is defined to be in between '(' and ')'.
    temp_buffer = []
    expressions = []
    for index, char in enumerate(requirement):
        if char == '(':
            temp_buffer.append(index)
        if char == ')':
            expressions.append(requirement[temp_buffer.pop() + 1:index])

    # Get the lowest expressions.
    expressions: List[str] = [expression for expression in expressions if ('(' or ')') not in expression]

    # Evaluate the lowest expressions
    for expression in expressions:
        expression_valid, expression_messages = _evaluate_expression(expression=expression, data=data)
        requirement = requirement.replace("(" + expression + ")", str(expression_valid))
        messages = messages + expression_messages

    try:
        # Evaluate the complete requirement, where the single expressions are replaced with the evaluated ones.
        valid = eval(requirement, {})

        # Make sure that valid is a boolean.
        if type(valid) is not bool:
            raise Exception(f"Evaluation of requirement '{requirement}' did not return a boolean.")
    except Exception as e:
        raise Exception(f"Could not evaluate requirement '{requirement}': " + str(e))

    return valid, messages


def format_message(messages: List[Dict[str, Union[List[str], str]]]) -> List[str]:
    """
    This function flattens the message object from the validate function.
    Means, the dictionary is converted to a simple list of all messages.
    The requirement entries are placed inside the message string. Each list element starts with \n.
    If no message for a requirement exists, it is removed.

    :param messages: The message object received from the validate function.

    :returns: A list of all messages.
    """
    formatted_messages = []

    # The messages object looks like this:
    # [{'requirement': '(key * with str/int/bool)',
    # 'messages': ["Value '1.89' of key 'additionalProp1' is not of type str/int/bool."]}]
    # We format it to this:
    # ["(key * with str/int/bool): Value '1.89' of key 'additionalProp1' is not of type str/int/bool."]
    for item in messages:
        messages_per_req = item.get("messages", [])
        requirement = item.get("requirement", "(Unknown requirement)")
        for message in messages_per_req:
            formatted_messages.append(f"\n{requirement}: {message}")
    # Remove duplicates from the list.
    formatted_messages = list(dict.fromkeys(formatted_messages))
    return formatted_messages


def validate(data: dict, requirements: List[str]) -> Tuple[bool, int, List[Dict[str, Union[List[str], str]]]]:
    """
    Validates the given data in dependence of the requirements.

    :param data: The data to be validated as dictionary.
    :param requirements: List of requirements (see README.md for further information).

    :returns: Is the data valid, the index of the first valid requirement (-1 if no requirement is valid),
    and a dict with the requirement (key: requirement) and the according validation messages (key: messages).
    """
    messages: List[Dict[str, Union[List[str], str]]] = []

    if not requirements:
        # If there are no requirements (empty list), we directly return.
        return True, -1, messages

    requirement_results = []
    for requirement in requirements:
        try:
            requirement_valid, requirement_messages = _evaluate_requirement(requirement=requirement.strip(),
                                                                            data=data)
        except Exception as e:
            # Something unexpected went wrong.
            raise ChildProcessError(f"Could not evaluate requirement '{requirement}': " + str(e))

        messages.append({"requirement": requirement, "messages": requirement_messages})
        requirement_results.append(requirement_valid)

    try:
        requirement_index = requirement_results.index(True)
        valid = True
    except ValueError:
        valid = False
        requirement_index = -1

    return valid, requirement_index, messages
