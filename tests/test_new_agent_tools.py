"""新增 Agent 工具（calculator / datetime_calculator / unit_converter）单测。

三个都是无状态、不需要网络/exec 权限的纯计算工具，不需要 DB，随 `python -m unittest` 全量跑。
"""
import json
import unittest

from service.tools.calculator import CalculatorTool, SafeEvalError, safe_eval
from service.tools.datetime_calculator import DatetimeCalculatorTool
from service.tools.unit_converter import UnitConverterTool


class CalculatorToolTest(unittest.TestCase):
    def setUp(self):
        self.tool = CalculatorTool()

    def test_basic_arithmetic(self):
        result = json.loads(self.tool.execute(expression="(1+2)*3"))
        self.assertEqual(result["result"], 9)

    def test_functions_and_constants(self):
        result = json.loads(self.tool.execute(expression="sqrt(16) + round(2.6)"))
        self.assertEqual(result["result"], 7.0)

    def test_division_by_zero_reports_error_not_crash(self):
        result = json.loads(self.tool.execute(expression="1/0"))
        self.assertIn("error", result)

    def test_empty_expression_reports_error(self):
        result = json.loads(self.tool.execute(expression=""))
        self.assertIn("error", result)

    def test_rejects_arbitrary_code_injection(self):
        """安全性回归：不能通过表达式访问属性/内置函数逃逸沙箱。"""
        dangerous = [
            "__import__('os').system('echo pwned')",
            "().__class__.__bases__",
            "open('/etc/passwd').read()",
        ]
        for expr in dangerous:
            with self.assertRaises(SafeEvalError):
                safe_eval(expr)

    def test_huge_exponent_rejected(self):
        with self.assertRaises(SafeEvalError):
            safe_eval("9**9**9")

    def test_tool_schema_shape(self):
        self.assertEqual(self.tool.get_name(), "calculator")
        self.assertIn("expression", self.tool.get_parameters()["required"])


class DatetimeCalculatorToolTest(unittest.TestCase):
    def setUp(self):
        self.tool = DatetimeCalculatorTool()

    def test_now_returns_date_and_weekday(self):
        result = json.loads(self.tool.execute(op="now"))
        self.assertIn("date", result)
        self.assertIn("weekday", result)

    def test_diff_between_two_dates(self):
        result = json.loads(self.tool.execute(op="diff", date1="2026-01-01", date2="2026-01-11"))
        self.assertEqual(result["days_between"], 10)

    def test_diff_handles_negative_direction(self):
        result = json.loads(self.tool.execute(op="diff", date1="2026-01-11", date2="2026-01-01"))
        self.assertEqual(result["days_between"], -10)

    def test_add_days_crosses_month_boundary(self):
        result = json.loads(self.tool.execute(op="add", date="2026-01-28", days=5))
        self.assertEqual(result["result"], "2026-02-02")

    def test_add_negative_days(self):
        result = json.loads(self.tool.execute(op="add", date="2026-03-01", days=-1))
        self.assertEqual(result["result"], "2026-02-28")

    def test_weekday_known_date(self):
        # 2026-01-01 是星期四
        result = json.loads(self.tool.execute(op="weekday", date="2026-01-01"))
        self.assertEqual(result["weekday"], "星期四")

    def test_invalid_date_format_reports_error(self):
        result = json.loads(self.tool.execute(op="weekday", date="not-a-date"))
        self.assertIn("error", result)

    def test_unknown_op_reports_error(self):
        result = json.loads(self.tool.execute(op="teleport"))
        self.assertIn("error", result)


class UnitConverterToolTest(unittest.TestCase):
    def setUp(self):
        self.tool = UnitConverterTool()

    def test_length_km_to_m(self):
        result = json.loads(self.tool.execute(value=2, from_unit="km", to_unit="m"))
        self.assertEqual(result["result"], 2000.0)

    def test_weight_jin_to_kg(self):
        result = json.loads(self.tool.execute(value=1, from_unit="斤", to_unit="kg"))
        self.assertEqual(result["result"], 0.5)

    def test_temperature_celsius_to_fahrenheit(self):
        result = json.loads(self.tool.execute(value=100, from_unit="celsius", to_unit="fahrenheit"))
        self.assertEqual(result["result"], 212.0)

    def test_temperature_celsius_to_kelvin(self):
        result = json.loads(self.tool.execute(value=0, from_unit="celsius", to_unit="kelvin"))
        self.assertEqual(result["result"], 273.15)

    def test_cross_category_conversion_rejected(self):
        result = json.loads(self.tool.execute(value=1, from_unit="kg", to_unit="m"))
        self.assertIn("error", result)

    def test_unit_lookup_is_case_and_whitespace_insensitive(self):
        # 模型传参不一定和表里的 key 大小写一致（比如 "KM" 而不是 "km"）；表里的 key 全是小写，
        # 查表前必须先归一化，否则会被误判成"不支持换算"
        result = json.loads(self.tool.execute(value=2, from_unit=" KM ", to_unit="M"))
        self.assertEqual(result["result"], 2000.0)

    def test_missing_params_reports_error(self):
        result = json.loads(self.tool.execute(value=1, from_unit="kg"))
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
