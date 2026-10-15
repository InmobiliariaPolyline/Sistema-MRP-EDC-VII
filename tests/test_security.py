"""Bloqueo por intentos fallidos y política de contraseñas."""
import unittest

from modules import security


class LockoutTests(unittest.TestCase):
    def setUp(self):
        self.reg: dict = {}

    def fail(self, user="Luis", now=1000.0):
        return security.register_failure(user, now=now, registry=self.reg)

    def test_locks_after_max_attempts_and_reports_remaining_attempts(self):
        lefts = [self.fail()[0] for _ in range(security.MAX_ATTEMPTS - 1)]
        self.assertEqual(lefts, [4, 3, 2, 1])
        left, locked = self.fail()
        self.assertEqual((left, locked), (0, security.LOCK_SECONDS))
        self.assertGreater(security.lock_remaining("Luis", now=1001.0, registry=self.reg), 0)

    def test_lock_expires_and_counter_restarts(self):
        for _ in range(security.MAX_ATTEMPTS):
            self.fail()
        later = 1000.0 + security.LOCK_SECONDS + 1
        self.assertEqual(security.lock_remaining("Luis", now=later, registry=self.reg), 0)
        self.assertEqual(self.fail(now=later)[0], security.MAX_ATTEMPTS - 1)

    def test_user_name_is_case_and_space_insensitive(self):
        for _ in range(security.MAX_ATTEMPTS):
            self.fail("LUIS")
        self.assertGreater(security.lock_remaining("  luis ", now=1001.0, registry=self.reg), 0)

    def test_unknown_names_are_counted_too_so_users_are_not_revealed(self):
        for _ in range(security.MAX_ATTEMPTS):
            self.fail("no-existe")
        self.assertGreater(security.lock_remaining("no-existe", now=1001.0, registry=self.reg), 0)

    def test_success_clears_the_failures(self):
        self.fail()
        self.fail()
        security.register_success("luis", registry=self.reg)
        self.assertEqual(self.fail()[0], security.MAX_ATTEMPTS - 1)

    def test_other_users_are_not_affected(self):
        for _ in range(security.MAX_ATTEMPTS):
            self.fail("ana")
        self.assertEqual(security.lock_remaining("luis", now=1001.0, registry=self.reg), 0)


class PasswordPolicyTests(unittest.TestCase):
    def test_valid_password(self):
        self.assertEqual(security.password_issues("Obra2026x", "luis"), [])

    def test_too_short(self):
        self.assertTrue(security.password_issues("ab1"))

    def test_needs_letters_and_numbers(self):
        self.assertTrue(security.password_issues("soloLetrasAqui"))
        self.assertTrue(security.password_issues("123456789012"))

    def test_common_and_same_as_user_are_rejected(self):
        self.assertTrue(security.password_issues("password1"))
        self.assertTrue(security.password_issues("luis12345", "LUIS12345"))

    def test_empty_and_too_long_for_bcrypt(self):
        self.assertTrue(security.password_issues("   "))
        self.assertTrue(security.password_issues("a1" * 40))  # 80 bytes > 72


if __name__ == "__main__":
    unittest.main()
