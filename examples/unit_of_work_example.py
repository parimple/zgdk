"""
Example of using Unit of Work pattern for complex transactions.

This example shows how to use the new Unit of Work pattern to perform
complex database operations with proper transaction management.
"""

from typing import Optional
import discord
from discord.ext import commands


class UnitOfWorkExampleCog(commands.Cog):
    """Example cog demonstrating Unit of Work pattern usage."""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name="uow_example")
    @commands.is_owner()
    async def unit_of_work_example(self, ctx, member: discord.Member):
        """
        Example command demonstrating Unit of Work pattern.
        
        This command shows how to:
        1. Use Unit of Work for transaction management
        2. Access multiple repositories within a single transaction
        3. Perform complex operations with automatic rollback on errors
        """
        
        # Example 1: Using the new get_unit_of_work method
        async with self.bot.get_unit_of_work() as uow:
            try:
                # Get or create member
                db_member = await uow.members.get_by_discord_id(member.id)
                if not db_member:
                    db_member = await uow.members.create_member(
                        discord_id=member.id,
                        joined_at=member.joined_at
                    )
                
                # Add activity points
                await uow.activities.add_activity(
                    member_id=db_member.id,
                    points=10,
                    activity_type="bonus"
                )
                
                # Update wallet balance
                await uow.members.update_wallet_balance(
                    db_member.id, 
                    db_member.wallet_balance + 100
                )
                
                # All operations will be committed automatically
                # If any error occurs, everything will be rolled back
                
                await ctx.send(f"✅ Successfully processed UoW example for {member.mention}")
                
            except Exception as e:
                # Automatic rollback will occur
                await ctx.send(f"❌ Error in UoW example: {str(e)}")
    
    @commands.command(name="uow_complex")
    @commands.is_owner()
    async def complex_transaction_example(self, ctx, member: discord.Member):
        """
        Advanced example with manual commit control.
        """
        
        async with self.bot.get_db() as session:
            # Create Unit of Work manually for fine-grained control
            uow = self.bot.service_container.create_unit_of_work(session)
            
            async with uow:
                try:
                    # Perform multiple related operations
                    db_member = await uow.members.get_by_discord_id(member.id)
                    
                    if db_member:
                        # Get member's current activity
                        activities = await uow.activities.get_member_activity(
                            member_id=db_member.id,
                            activity_type="bonus"
                        )
                        
                        total_bonus_points = sum(act.points for act in activities)
                        
                        # Complex business logic
                        if total_bonus_points > 1000:
                            # Award special achievement
                            await uow.activities.add_activity(
                                member_id=db_member.id,
                                points=500,
                                activity_type="achievement"
                            )
                            
                            # Update wallet with bonus
                            new_balance = db_member.wallet_balance + 1000
                            await uow.members.update_wallet_balance(
                                db_member.id, 
                                new_balance
                            )
                            
                            result_msg = f"🎉 {member.mention} earned special achievement! +1000 wallet bonus!"
                        else:
                            result_msg = f"📊 {member.mention} has {total_bonus_points} bonus points (need 1000 for achievement)"
                    else:
                        result_msg = f"❌ Member {member.mention} not found in database"
                    
                    # Manual commit for fine control
                    await uow.commit()
                    await ctx.send(result_msg)
                    
                except Exception as e:
                    # uow will automatically rollback in __aexit__
                    await ctx.send(f"❌ Complex transaction failed: {str(e)}")


async def setup(bot):
    """Setup function to load the cog."""
    await bot.add_cog(UnitOfWorkExampleCog(bot))