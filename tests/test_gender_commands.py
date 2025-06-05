"""Test gender commands functionality."""

import asyncio
import pytest
import discord
from unittest.mock import AsyncMock, MagicMock, patch

# Test configuration
TEST_GUILD_ID = 960665311701528596
MALE_ROLE_ID = 960665311701528599
FEMALE_ROLE_ID = 960665311701528600
TEST_USER_ID = 123456789


class MockRole:
    """Mock role object."""
    
    def __init__(self, role_id: int, name: str):
        self.id = role_id
        self.name = name
        
    def __eq__(self, other):
        return isinstance(other, MockRole) and self.id == other.id


class MockMember:
    """Mock member object."""
    
    def __init__(self, user_id: int, roles=None):
        self.id = user_id
        self.mention = f"<@{user_id}>"
        self.roles = roles or []
        
    async def add_roles(self, *roles, reason=None):
        """Mock add_roles method."""
        for role in roles:
            if role not in self.roles:
                self.roles.append(role)
                
    async def remove_roles(self, *roles, reason=None):
        """Mock remove_roles method."""
        for role in roles:
            if role in self.roles:
                self.roles.remove(role)


class MockGuild:
    """Mock guild object."""
    
    def __init__(self):
        self.id = TEST_GUILD_ID
        self.male_role = MockRole(MALE_ROLE_ID, "♂")
        self.female_role = MockRole(FEMALE_ROLE_ID, "♀")
        
    def get_role(self, role_id: int):
        """Mock get_role method."""
        if role_id == MALE_ROLE_ID:
            return self.male_role
        elif role_id == FEMALE_ROLE_ID:
            return self.female_role
        return None


class MockContext:
    """Mock context object."""
    
    def __init__(self):
        self.guild = MockGuild()
        self.author = MockMember(999999999)
        self.responses = []
        
    async def send(self, content=None, **kwargs):
        """Mock send method."""
        self.responses.append(content)


class MockBot:
    """Mock bot object."""
    
    def __init__(self):
        self.config = {
            "gender_roles": {
                "male": MALE_ROLE_ID,
                "female": FEMALE_ROLE_ID
            }
        }


def test_male_command_new_user():
    """Test `,male` command for user without any gender role."""
    from cogs.commands.mod import ModCog
    
    # Setup
    bot = MockBot()
    mod_cog = ModCog(bot)
    ctx = MockContext()
    user = MockMember(TEST_USER_ID)
    
    # Run test
    async def run_test():
        await mod_cog.male(ctx, user)
        
        # Verify results
        assert len(ctx.responses) == 1
        assert "✅ Nadano rolę **♂**" in ctx.responses[0]
        assert ctx.guild.male_role in user.roles
        assert ctx.guild.female_role not in user.roles
    
    asyncio.run(run_test())


def test_male_command_already_male():
    """Test `,male` command for user who already has male role."""
    from cogs.commands.mod import ModCog
    
    # Setup
    bot = MockBot()
    mod_cog = ModCog(bot)
    ctx = MockContext()
    user = MockMember(TEST_USER_ID, roles=[ctx.guild.male_role])
    
    # Run test
    async def run_test():
        await mod_cog.male(ctx, user)
        
        # Verify results
        assert len(ctx.responses) == 1
        assert "ℹ️" in ctx.responses[0] and "już ma rolę męską" in ctx.responses[0]
        assert ctx.guild.male_role in user.roles
    
    asyncio.run(run_test())


def test_male_command_switch_from_female():
    """Test `,male` command for user switching from female to male."""
    from cogs.commands.mod import ModCog
    
    # Setup
    bot = MockBot()
    mod_cog = ModCog(bot)
    ctx = MockContext()
    user = MockMember(TEST_USER_ID, roles=[ctx.guild.female_role])
    
    # Run test
    async def run_test():
        await mod_cog.male(ctx, user)
        
        # Verify results
        assert len(ctx.responses) == 1
        assert "✅ Nadano rolę **♂**" in ctx.responses[0]
        assert ctx.guild.male_role in user.roles
        assert ctx.guild.female_role not in user.roles
    
    asyncio.run(run_test())


def test_female_command_new_user():
    """Test `,female` command for user without any gender role."""
    from cogs.commands.mod import ModCog
    
    # Setup
    bot = MockBot()
    mod_cog = ModCog(bot)
    ctx = MockContext()
    user = MockMember(TEST_USER_ID)
    
    # Run test
    async def run_test():
        await mod_cog.female(ctx, user)
        
        # Verify results
        assert len(ctx.responses) == 1
        assert "✅ Nadano rolę **♀**" in ctx.responses[0]
        assert ctx.guild.female_role in user.roles
        assert ctx.guild.male_role not in user.roles
    
    asyncio.run(run_test())


def test_female_command_already_female():
    """Test `,female` command for user who already has female role."""
    from cogs.commands.mod import ModCog
    
    # Setup
    bot = MockBot()
    mod_cog = ModCog(bot)
    ctx = MockContext()
    user = MockMember(TEST_USER_ID, roles=[ctx.guild.female_role])
    
    # Run test
    async def run_test():
        await mod_cog.female(ctx, user)
        
        # Verify results
        assert len(ctx.responses) == 1
        assert "ℹ️" in ctx.responses[0] and "już ma rolę kobiecą" in ctx.responses[0]
        assert ctx.guild.female_role in user.roles
    
    asyncio.run(run_test())


def test_female_command_switch_from_male():
    """Test `,female` command for user switching from male to female."""
    from cogs.commands.mod import ModCog
    
    # Setup
    bot = MockBot()
    mod_cog = ModCog(bot)
    ctx = MockContext()
    user = MockMember(TEST_USER_ID, roles=[ctx.guild.male_role])
    
    # Run test
    async def run_test():
        await mod_cog.female(ctx, user)
        
        # Verify results
        assert len(ctx.responses) == 1
        assert "✅ Nadano rolę **♀**" in ctx.responses[0]
        assert ctx.guild.female_role in user.roles
        assert ctx.guild.male_role not in user.roles
    
    asyncio.run(run_test())


def test_gender_commands_no_config():
    """Test gender commands when configuration is missing."""
    from cogs.commands.mod import ModCog
    
    # Setup
    bot = MockBot()
    bot.config = {}  # No gender_roles config
    mod_cog = ModCog(bot)
    ctx = MockContext()
    user = MockMember(TEST_USER_ID)
    
    # Run test
    async def run_test():
        await mod_cog.male(ctx, user)
        await mod_cog.female(ctx, user)
        
        # Verify results
        assert len(ctx.responses) == 2
        assert "❌ Role płci nie są skonfigurowane" in ctx.responses[0]
        assert "❌ Role płci nie są skonfigurowane" in ctx.responses[1]
    
    asyncio.run(run_test())


if __name__ == "__main__":
    print("Uruchamianie testów komend gender...")
    
    # Lista testów do uruchomienia
    test_functions = [
        test_male_command_new_user,
        test_male_command_already_male,
        test_male_command_switch_from_female,
        test_female_command_new_user,
        test_female_command_already_female,
        test_female_command_switch_from_male,
        test_gender_commands_no_config
    ]
    
    passed = 0
    failed = 0
    
    for test_func in test_functions:
        try:
            test_func()
            print(f"✅ {test_func.__name__}")
            passed += 1
        except Exception as e:
            print(f"❌ {test_func.__name__}: {e}")
            failed += 1
    
    print(f"\nWyniki: {passed} ✅ | {failed} ❌")
    
    if failed == 0:
        print("🎉 Wszystkie testy przeszły!")
    else:
        print("⚠️ Niektóre testy nie przeszły.") 