package search

import (
	"fmt"
)

type KMPSearcher struct {
	// the pattern to find in the raw text
	pattern string
	// prefix-indexes
	pi []int
}

func (k *KMPSearcher) String() string {
	return fmt.Sprintf("Kmp-Searcher: Initialzied with pattern - %s", k.pattern)
}

// find all the matches for the pattern in the provided text
func (k *KMPSearcher) FindAll(text []byte) []Match {
	return nil
}

func NewKmp(pattern string) *KMPSearcher {
	return &KMPSearcher{
		pattern: pattern,
	}
}
