package main

import (
	"flag"
	"fmt"
	"io"
)

type Config struct {
	Algo         string
	PatternsFile string
	CountOnly    bool
	Pattern      string
	Path         string
}

// func ParseArgs(args []string)
