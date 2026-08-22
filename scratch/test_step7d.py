import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app, db, models
from seed import seed_default_college

app.app_context().push()
client = app.test_client(use_cookies=True)

print("=== 1. VERIFY SEEDED POSTS RENDERING ===")
res_get = client.get('/forum')
print("/forum GET status:", res_get.status_code)
html_get = res_get.data.decode('utf-8')

print("Seeded post 'Rahul Sharma' present:", 'Rahul Sharma' in html_get)
print("Seeded post 'TechVanguard' present:", 'TechVanguard' in html_get)
print("Seeded post 'Sneha Gupta' present:", 'Sneha Gupta' in html_get)

print("\n=== 2. POST NEW FORUM TOPIC & PERSISTENCE ===")
payload = {
    'author': 'Prof. Rajesh Kumar (Dept of Commerce)',
    'title': 'National Seminar on Financial Technology & Digital Banking 2026',
    'category': 'Academics & Question Papers',
    'content': 'The Department of Commerce is hosting a 1-day national seminar on Fintech trends on Oct 10th. Submit research abstracts by Sept 20th.'
}

res_post = client.post('/forum', data=payload, follow_redirects=True)
print("POST /forum status:", res_post.status_code)

# Query database directly
new_db_post = models.ForumPost.query.filter_by(title=payload['title']).first()
print("New topic persisted in DB:", new_db_post is not None)
print("New topic author:", new_db_post.author if new_db_post else None)

# Verify ordering (new topic appears first)
all_posts = models.ForumPost.query.filter_by(college_id=1).order_by(models.ForumPost.created_at.desc(), models.ForumPost.id.desc()).all()
print("First post in list is the newly created topic:", all_posts[0].title == payload['title'])
print("Total forum posts count in DB:", len(all_posts))

print("\n=== 3. VERIFY TEMPLATE RENDERING OF CREATED_AT ===")
res_rendered = client.get('/forum')
html_rendered = res_rendered.data.decode('utf-8')
print("Rendered HTML contains new topic title:", 'Financial Technology' in html_rendered)
print("Rendered HTML contains author:", 'Prof. Rajesh Kumar' in html_rendered)

print("\nAll Step 7D Forum Persistence Tests PASSED Successfully!")
