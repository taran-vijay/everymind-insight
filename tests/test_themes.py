import pandas as pd

from everymind_insight.themes import analyze_themes


def test_topics_are_mentions_not_sentiment_and_unmatched_is_explicit():
    frame = pd.DataFrame({'is_usable_id': [True] * 6 + [False],
                          'valuable_comment': ['988 resources', 'crisis warning signs', '', None, 'unmatched phrase', 'recursos en español', '988'],
                          'improve_comment': ['More practice examples', 'No more examples please', 'nothing', 'nothing about the crisis was explained', 'unmatched phrase', None, 'practice']})
    metrics, data, review = analyze_themes(frame, present_questions={'valuable_comment', 'improve_comment'}, input_hash='a' * 64, config_hash='b' * 64)
    find = lambda identifier, question, theme=None: next(m for m in metrics if m.metric_id == identifier and m.dimensions.get('question') == question and (theme is None or m.dimensions.get('theme') == theme))
    assert find('comment_answered', 'valuable_comment').value == 4
    assert find('comment_unclassified', 'valuable_comment').value == 2
    assert find('theme_prevalence', 'improve_comment', 'practice').numerator == 2
    assert find('theme_prevalence', 'improve_comment', 'no_change').numerator == 1
    assert all('text' not in row and 'id' not in row for row in review)
    assert len(data.questions) == 2
