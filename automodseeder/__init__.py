from .automodseeder import AutoModSeeder


def setup(bot):
    bot.add_cog(AutoModSeeder(bot))
