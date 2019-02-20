from collections import Counter

from itertools import combinations as C

class UnigramReader(object):
    def __init__(self, vocab_file):
        self.unigrams = Counter()
        with open(vocab_file) as f:
            for i, line in enumerate(f):
                _, count = line.strip().split()
                self.unigrams[i] = int(count)

class BigramReader(object):
    def __init__(self, training_file):
        self.bigrams = Counter()
        with open(training_file) as f:
            for line in f:
                label, *word_occurrences = line.strip().split()
                counts = {int(word) for word, _ in map(lambda s: s.split(":"), word_occurrences)}
                for (w_i, w_j) in C(counts, 2):
                    # If we've previously stored this in a different order, keep storing it that way
                    if self.bigrams[(w_j, w_i)] != 0:
                        self.bigrams[(w_j, w_i)] += 1
                    else:
                        self.bigrams[(w_i, w_j)] += 1

if __name__ == "__main__":
    import sys
    reader = BigramReader(sys.argv[1])
    print(reader.bigrams.most_common(10))