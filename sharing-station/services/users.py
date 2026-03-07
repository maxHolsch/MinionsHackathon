class UserService:
    """In-memory user store. Swap for Supabase later."""

    def __init__(self):
        self.users = {
            "peter": {
                "name": "Peter",
                "nickname": "Tiger",
                "memories": ["Loves sci-fi books", "Plays Catan every Thursday"],
                "preferences": "science fiction, strategy games",
            },
            "alice": {
                "name": "Alice",
                "nickname": None,
                "memories": [],
                "preferences": None,
            },
        }

    def get(self, user_id):
        return self.users.get(user_id)

    def update(self, user_id, nickname=None, memory=None, preferences=None):
        if user_id not in self.users:
            self.users[user_id] = {
                "name": user_id,
                "nickname": None,
                "memories": [],
                "preferences": None,
            }
        user = self.users[user_id]
        if nickname:
            user["nickname"] = nickname
        if memory:
            user["memories"].append(memory)
        if preferences:
            user["preferences"] = preferences
