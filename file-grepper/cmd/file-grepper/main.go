package main

import (
	"flag"
	"fmt"
	"strings"
	"errors"
)

func ParseFlags(){
	var pattern = flag.String("pattern", "gopher", "pattern to be searched for")
	
}

func main() {
	fmt.Println("Hi there from file-grepper")
}
