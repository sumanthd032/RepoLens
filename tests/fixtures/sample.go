// Package sample is a fixture for Go parser tests.
package sample

import "fmt"

// Server handles incoming routes.
type Server struct {
	port int
}

// Router dispatches requests.
type Router interface {
	Handle(path string) error
}

// handleRoute processes a single route and returns an error.
func handleRoute(path string) error {
	if path == "" {
		return fmt.Errorf("empty path")
	}
	return nil
}

// Start launches the server on its configured port.
func (s *Server) Start() error {
	fmt.Printf("listening on %d\n", s.port)
	return handleRoute("/")
}
