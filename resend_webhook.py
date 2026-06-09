import json
import httpx

# Load today's top post
with open('posts_output/2026-06-04/posts.json', 'r', encoding='utf-8') as f:
    posts = json.load(f)

top = posts[0]
meta = top.get('_meta', {})
text_post = top.get('text_post', {})
carousel = top.get('carousel', {})
short_take = top.get('short_take', {})

payload = {
    'post_content': text_post.get('content', ''),
    'post_type': top.get('content_type_recommendation', 'Text Post'),
    'hashtags': text_post.get('hashtags', []),
    'hook': text_post.get('hook', ''),
    'carousel_caption': carousel.get('caption', ''),
    'short_take_line1': short_take.get('line1', ''),
    'short_take_line2': short_take.get('line2', ''),
    'story_title': meta.get('story_title', ''),
    'source': meta.get('source', ''),
    'date': '2026-06-04',
}

print('Firing webhook...')
print('Story:', meta.get('story_title', ''))
print('Content length:', len(payload['post_content']), 'chars')
print()

resp = httpx.post(
    'https://hook.eu1.make.com/6w0cw4xmkatq364ww3eap92szk5hjlak',
    json=payload,
    timeout=30,
    headers={'Content-Type': 'application/json'}
)
print('Webhook HTTP status:', resp.status_code)
print('Response body:', resp.text)
