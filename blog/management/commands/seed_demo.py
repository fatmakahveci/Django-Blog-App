from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from blog.models import Category, Post, Tag


# Stable slugs make repeated runs safe; existing editorial changes are preserved.
ARTICLES = [
    ('less-noise-more-ideas', 'Less noise. More room for ideas.', 'Everyday life', 'sage',
     'We do not have to fill every quiet moment. Sometimes the best idea arrives in the small space we leave open.', ['focus', 'creativity']),
    ('a-simpler-interface', 'A better interface starts with less', 'Design', 'ink',
     'The character of a product lives in what it leaves out, too. A few practical notes on making room for what matters.', ['design', 'simplicity']),
    ('from-idea-to-product', 'From a small idea to something real', 'Technology', 'clay',
     'Start with something small that works. Let real people help you discover what the next version should become.', ['software', 'making']),
    ('learning-to-read-slowly', 'Learning to read slowly again', 'Everyday life', 'sky',
     'A good page is more than a step toward finishing a book. It is a place to pause, notice, and let your attention return.', ['reading', 'focus']),
    ('the-person-behind-the-code', 'Remember the person behind the code', 'Technology', 'sage',
     'Good software is written for people as well as machines. Leave something clear for the next person who opens the file.', ['software', 'simplicity']),
    ('the-power-of-space', 'Let the empty space say something', 'Design', 'clay',
     'On a page, in a room, or in a busy day: a little breathing room helps everything else make sense.', ['design', 'creativity']),
    ('small-habits-long-shadows', 'Small habits cast long shadows', 'Everyday life', 'ink',
     'Lasting change often begins with an ordinary action repeated. Build a rhythm that fits the life you actually have.', ['focus', 'making']),
    ('stay-curious', 'Stay curious, like a beginner', 'Technology', 'sky',
     'Knowing more does not mean asking fewer questions. A small experiment can turn an unfamiliar subject into a useful discovery.', ['software', 'reading']),
]

PARAGRAPHS = [
    [
        'The day often starts before we have decided what deserves our attention. A screen lights up, a list grows, and the first quiet hour disappears into other people’s priorities. Choosing one thing to notice is a modest way to begin again. Before opening the next tab, ask: what would I like to understand a little better today?',
        'That question does not require a perfect routine. A single page in a notebook can be enough. Write down something you observed, something that surprised you, and something you still do not understand. The point is to make a little space between receiving information and immediately moving on.',
        'A walk can serve the same purpose. Without a queue of things to listen to, familiar streets become interesting again. You notice how a sign is worded, where people choose to sit, or how a shop makes its entrance inviting. Ideas often begin as these small, unplanned observations.',
        'When an idea does arrive, resist asking it to become a complete project immediately. Make a rough sketch. Explain it in one sentence. Share it with someone who will ask an honest question. A small experiment teaches more than a perfect plan that never meets the world.',
        'There will still be busy days and unfinished notes. The aim is not to remove every distraction or turn rest into another task. It is simply to protect a few moments in which your own curiosity can be heard. Start with ten minutes. Leave the rest of the page open.',
    ],
    [
        'A screen can contain many useful controls and still be difficult to use. Each button asks a person to make a decision. When those decisions compete, even a simple task starts to feel complicated. Begin by identifying the one action someone came here to complete.',
        'Walk through that task with a fresh set of eyes. Notice where the interface asks for information it already has, where labels require explanation, and where an option interrupts the main flow. Removing one unnecessary decision can be more helpful than adding a new shortcut.',
        'Simplicity is not the same as hiding everything. A secondary action still needs a sensible home, clear wording, and a way to be found with a keyboard. Show the right amount of detail at the moment it becomes useful.',
        'Test the result with a realistic task. Watch where people hesitate before explaining the design. Their pauses are valuable evidence. A quieter interface succeeds when people can move forward with confidence, even if they never notice the work that made it possible.',
    ],
    [
        'A promising idea can become heavy when every possible feature is added to the plan. Instead, choose one person, one problem, and one complete path through a small solution. A narrow product can still feel finished when that path works well.',
        'Write down what you expect to happen before building. Perhaps someone will find an article faster, finish a form without help, or return to a saved item. An observable outcome gives the first version a purpose beyond simply existing.',
        'Build enough to test that expectation. Keep the surrounding structure easy to change. Clear names, a short setup guide, and a few tests around important behavior make it easier to learn without breaking what already works.',
        'Put the result in front of a real person and listen. Some assumptions will survive; others will not. Record the surprise, choose the next smallest improvement, and repeat. Progress becomes easier to see when each version answers a specific question.',
    ],
    [
        'Reading can quietly turn into collecting finished books, saved links, and highlighted sentences. The collection grows while individual ideas become harder to remember. Slowing down begins with giving one page enough attention to leave an impression.',
        'Choose a short passage and read it without reaching for another tab. At the end, close the page and describe its main idea in your own words. The gaps in that explanation reveal where a second reading might be useful.',
        'Make a note only when something changes your understanding. A question, a disagreement, or a connection to another experience is more useful than copying a paragraph without context. Leave a sentence about why the passage mattered to you.',
        'Some days a few pages will be enough. The goal is not a slower number on a reading tracker. It is a richer conversation with what you read, and a little more room for the words to become part of your own thinking.',
    ],
    [
        'Every function has a future reader. Sometimes that person is a teammate; often it is you, several months after the details have faded. Good code leaves enough context for that reader to make a change without first reconstructing the entire project.',
        'Start with names that describe the role of a value or action. Keep related behavior close together. A comment earns its place when it explains a decision, a constraint, or a surprising edge case that the code alone cannot communicate.',
        'Tests are another form of explanation. A useful test describes what someone relies on: a private draft stays private, a saved link remains stable, or an invalid request cannot change data. Those promises are more durable than tests that repeat each implementation step.',
        'Before finishing a change, read the diff as if someone else wrote it. Remove abandoned paths, explain the important tradeoff, and leave clear instructions for verification. Consideration for the next reader is one of the simplest ways to make software last.',
    ],
    [
        'Empty space is an active part of a composition. It separates ideas, suggests relationships, and gives the eye somewhere to rest. Without it, even carefully chosen elements can feel as though they are speaking at the same time.',
        'Try grouping related details before changing their size or color. A title, a short description, and a date can form one clear unit when their spacing expresses that relationship. A larger gap then signals the beginning of something new.',
        'The same principle applies beyond a page. A meeting needs pauses for questions. A shelf needs room for the objects it holds. A schedule needs a little flexibility if the unexpected is to feel manageable rather than disruptive.',
        'Remove one element and look again. If the remaining parts become clearer, the space is doing useful work. Restraint is not an absence of care; it is a way of directing attention toward what deserves it.',
    ],
    [
        'A new habit often begins with an ambitious version of ourselves. That version has plenty of energy, an orderly calendar, and no interruptions. A lasting routine needs to work on an ordinary Tuesday as well.',
        'Choose an action small enough to repeat when enthusiasm is low. Write one sentence after breakfast. Review one task before closing your laptop. Put the book where you will see it instead of relying on a reminder you might dismiss.',
        'Attach the action to something that already happens. A familiar cue reduces the need to decide again each day. Keep a simple record if it helps, but do not let maintaining the record become more important than the activity itself.',
        'Missing a day is information, not a verdict. Adjust the size or timing and return to the next opportunity. The value of a small habit is not a flawless streak; it is a dependable path back to something you want to keep doing.',
    ],
    [
        'Experience gives us useful patterns, but those patterns can also make a familiar explanation feel inevitable. A beginner has the advantage of not yet knowing which questions are considered obvious. Borrowing that perspective can reveal an assumption worth examining.',
        'When approaching a new subject, write down three questions before searching for answers. Look for a primary source, try a small example, and keep track of where your expectation differs from what actually happens.',
        'Explain the result to someone outside the topic. Notice the words that require a definition and the steps you cannot yet connect. Clear explanations tend to grow from concrete examples rather than a longer list of impressive terms.',
        'Keep one unanswered question at the end of your notes. It gives your next session somewhere to begin. Curiosity does not require starting over every day; it asks that we leave enough room for what we do not know yet.',
    ],
]


def demo_body(index):
    return '\n\n'.join([
        ARTICLES[index][4], *PARAGRAPHS[index],
        'This is sample editorial content for Folio. You can edit or remove it and publish your own stories in the editor dashboard.',
    ])


class Command(BaseCommand):
    help = 'Add English sample articles without overwriting existing content or creating a login account.'

    @transaction.atomic
    def handle(self, *args, **options):
        author, created = get_user_model().objects.get_or_create(
            username='folio-demo',
            defaults={'first_name': 'Folio', 'last_name': 'Editor', 'is_active': False},
        )
        if created:
            author.set_unusable_password()
            author.save(update_fields=['password'])
        count = 0
        for index, (slug, title, topic, cover, excerpt, names) in enumerate(ARTICLES):
            category, _ = Category.objects.get_or_create(name=topic)
            post, created = Post.objects.get_or_create(
                slug=f'demo-{slug}',
                defaults={
                    'title': title, 'excerpt': excerpt, 'body': demo_body(index),
                    'author': author, 'category': category, 'status': Post.Status.PUBLISHED,
                    'published_at': timezone.now() - timedelta(days=index + 1),
                    'featured': index == 0, 'cover_style': cover,
                },
            )
            if created:
                post.tags.set([Tag.objects.get_or_create(name=name)[0] for name in names])
                count += 1
        self.stdout.write(self.style.SUCCESS(f'{count} sample articles added. Existing content was preserved.'))
