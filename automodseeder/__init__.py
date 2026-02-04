from .automodseeder import AutoModSeeder


async def setup(bot):
    await bot.add_cog(AutoModSeeder(bot))
