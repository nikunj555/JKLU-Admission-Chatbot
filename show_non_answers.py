import json

data = json.load(open('data/test/eval_200_results.json', encoding='utf-8'))
non_answers = [r for r in data['results'] if r['status'] != 'answer']
print(f"Total non-answers: {len(non_answers)}")
for r in non_answers:
    print(f"Q{r['id']}: [{r['status'].upper()}] {r['question']}")
    print(f"   Reason / Answer: {r['answer'][:120]}...\n")
