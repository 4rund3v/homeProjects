package search

import (
	"fmt"
	"strings"
)

const defaultSearchAlgo = "kmp"

// the simple factory which returns the abstract interface for searching
func NewSearcher(algo string, pattern string) (Searcher, error) {
	if algo == "" {
		algo = defaultSearchAlgo
	}
	switch strings.ToLower(algo) {
	case "kmp":
		return NewKmp(pattern), nil
	default:
		return nil, fmt.Errorf("unknown algo presented: %s", algo)
	}
}
