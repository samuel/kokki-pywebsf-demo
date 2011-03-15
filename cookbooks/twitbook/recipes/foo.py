
from kokki import File, Template

File("/tmp/foo",
    mode = 0600,
    content = Template("twitbook/foo.j2"))
