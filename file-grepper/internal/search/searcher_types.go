package search

// Match holds the file offset where the match is present
type Match struct {
	Offset int
}

// Searcher interface
type Searcher interface {
	// find all - given the text, finds all positions where the pattern matched the text
	FindAll(text []byte) []Match
}
