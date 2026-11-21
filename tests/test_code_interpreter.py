import unittest
from modules.code_engine import CodeEngine

class TestCodeInterpreter(unittest.TestCase):
    def setUp(self):
        self.engine = CodeEngine()

    def test_extract_code(self):
        text = "Here is some code:\n```python\nprint('hello')\n```\nHope it helps!"
        code = self.engine.extract_code(text)
        self.assertEqual(code, "print('hello')")

    def test_execute_python_success(self):
        code = "print('success_test')"
        result = self.engine.execute_python(code)
        self.assertTrue(result['success'])
        self.assertEqual(result['output'].strip(), "success_test")

    def test_execute_python_error(self):
        code = "print(1/0)"
        result = self.engine.execute_python(code)
        self.assertFalse(result['success'])
        self.assertIn("ZeroDivisionError", result['error'])

if __name__ == '__main__':
    unittest.main()
