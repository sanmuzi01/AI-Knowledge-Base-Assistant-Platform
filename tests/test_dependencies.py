import unittest
from unittest.mock import AsyncMock, patch

from sqlalchemy import inspect

from models.init_db import User
from service import dependencies


class CurrentUserDependencyTest(unittest.IsolatedAsyncioTestCase):
    async def test_seen_timestamp_is_not_left_dirty_after_committed_touch(self):
        user = User(id=1, name="admin", password="hash", is_disabled=0, last_seen_at=None)

        with (
            patch.object(dependencies, "_user_id_from_credentials", return_value=1),
            patch.object(dependencies, "get_user_by_id_async", new=AsyncMock(return_value=user)),
            patch.object(dependencies, "touch_user_seen_async", new=AsyncMock(return_value=True)) as touch,
        ):
            result = await dependencies.get_current_user_async(object(), async_db=object())

        self.assertIs(result, user)
        touch.assert_awaited_once()
        self.assertIsNotNone(user.last_seen_at)
        self.assertFalse(inspect(user).attrs.last_seen_at.history.has_changes())


if __name__ == "__main__":
    unittest.main()
