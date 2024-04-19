# Processors

Processors provide functionality to manipulate the given data object.
A list of all available processor modules and general information can be found in [modules](/docs/MODULES.md).

## Table of Contents

> * [Testing](#testing)
> * [Data Requirements](#data-requirements)

## Testing

You can provide test data using the `get_test_data` method.
If test data is provided, the processor module is automatically tested,
when executing the test framework (`src/test/test.py`).

Furthermore, available data requirements (see [Data Requirements](#data-requirements)) are tested.
Means, it is checked if they are in the required and correct format.

## Data Requirements

The requirements are used to validate the data input of processing modules. The _validate function returns `True`
or `False` and the index of the first valid requirement (otherwise `-1`) as well as a list of messages.

The requirements define what the data object (fields and tags) has to contain/or not contain.
A requirement consists of single expressions, embedded into `(` and `)` and chained by `and`.
An `or` is achieved by adding a new requirement to the requirement list.
Every expression has to be evaluable against the data object. Expressions are case-sensitive!

**Note:** If there are no requirements, just pass an empty list (e.g. `[]`).

Example:

```
['((key * with ints/floats) and (keys == 1))',
 '(key * with int/float)']
```

This would result in the following two acceptable data objects:

```json
{
  "test": [
    1,
    3,
    2
  ]
}
```

or

```json
{
  "test1": 1,
  "test2": 2,
  "test3": 3
}
```

#### Keywords

- **key**: Required key followed by the user-specific value. Can be combined with `with` (
  e.g. `(key test with int)`). Keys can also be inverted by `!` (e.g. every key except `(key !test with int)`). You can
  also accept all keys with `*` (e.g. every key `(key * with int)`). Note: Only keys without space are allowed.
- **keys**: Number of elements in the data object followed by an operator (`==`, `!=`, `>=`, `<=`, `<`, `>`) and
  integer (e.g. `(keys == 2)`).
- **length**: Check the length of lists (e.g. `length test1 == 1`, `length * equal`, `length !event == 1`,
  or `length test1 == test2`).
  The following operators are allowed: `==`, `!=`, `>=`, `<=`, `<`, `>`. Note: Only keys without space are allowed.
- **value**: Check the value of a key (e.g. `value event == "init"`, where `event` is the key).
  Note: Only keys without space are allowed. The following operators are allowed: `==`, `!=`, `>=`, `<=`, `<`, `>`.
  If the comparison value can be a float, integer, or boolean but should be a string, use `""` to encapsulate it:
  e.g. `(value string == "3")`, where `string` is `"3"` - evaluates `True`,
  whereby `(value string == 3)`, where `string` is `"3"` - evaluates `False`.

- **and**: Connecting expressions with an `and`.
- **or**: Connecting expressions with an `or`.


- **with**: Defining data types of key-values or data types of lists (e.g.: `(key * with ints)`).


- **()**: Capsule expressions.

#### Data Types:

- **int**: An integer.
- **float**: A float.
- **number**: A float or integer.
- **str**: A string.
- **bool**: A boolean.


- **list**: A list with items of undefined type.
- **ints**: A list of integers.
- **floats**: A list of floats.
- **numbers**: A list with floats or integers.
- **strs**: A list of strings.
- **bools**: A list of booleans.

You can combine data types: `int/ints`. Means, `int` or `ints` (e.g. `key * with int/ints`).

**Note:** Lists with multiple data types are currently not supported (expect `numbers`).
