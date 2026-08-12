# ModelForm

`ModelForm` auto-generates form fields from your model's columns and handles `save()` for you.

## Basic usage

```python
class PostForm(ModelForm):
    class Meta:
        model  = Post
        fields = ["title", "slug", "content", "is_published"]
```

`fields` controls which columns become form fields. Use `"__all__"` to include every column (except `id`).

## Excluding fields

```python
class PostForm(ModelForm):
    class Meta:
        model   = Post
        exclude = ["created_at", "updated_at"]
```

## Overriding auto-generated fields

Declare a field explicitly to override the auto-generated one:

```python
class PostForm(ModelForm):
    title = CharField(max_length=200, label="Post Title", help_text="Keep it concise.")

    class Meta:
        model  = Post
        fields = ["title", "slug", "content"]
```

## Column → field type mapping

| SQLAlchemy type | Form field |
|---|---|
| `String` | `CharField` |
| `Text` | `TextField` |
| `Integer` | `IntegerField` |
| `Float` | `FloatField` |
| `Numeric` | `DecimalField` |
| `Boolean` | `BooleanField` |
| `Date` | `DateField` |
| `DateTime` | `DateTimeField` |

## Create a new object

```python
form = PostForm(data=dict(await request.form()))
if await form.is_valid():
    post = await form.save()     # creates a new Post in the database
```

## Update an existing object

Pass `instance` to pre-fill the form and update instead of create:

```python
post = await Post.objects.get(id=pk)

# GET — display pre-filled form
form = PostForm(instance=post)

# POST — validate and save
form = PostForm(data=dict(await request.form()), instance=post)
if await form.is_valid():
    await form.save()   # updates existing post
```

## Save without committing

```python
if await form.is_valid():
    post = await form.save(commit=False)
    post.author_id = request.user.id   # set extra fields
    await post.save()
```

## HTML rendering

Render a form directly to HTML without writing a template loop:

```python
form = PostForm()

form.as_p()       # each field wrapped in <p>
form.as_table()   # each field as a <tr> (wrap in <table> yourself)
form.as_div()     # each field in <div class="form-group">
```

Each method emits labels, widgets, and inline error lists. Useful for quick prototypes or email bodies; use a custom template loop for full control over markup.
