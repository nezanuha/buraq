from buraq import models


class Profile(models.Model):
    user_id    = models.ForeignKey("buraq_users")
    bio        = models.TextField(null=True)
    avatar_url = models.CharField(max_length=500, null=True)
