package http

import (
	"net/http"

	"go-biz-engine/internal/config"
)

// Handler хранит зависимости (config и т.д.)
type Handler struct {
	cfg *config.Config
}

// NewHandler создаёт HTTP-хендлер с конфигом.
func NewHandler(cfg *config.Config) *Handler {
	return &Handler{cfg: cfg}
}

// Router регистрирует маршруты и возвращает http.Handler.
func (h *Handler) Router() http.Handler {
	mux := http.NewServeMux()

	mux.HandleFunc("/health", h.handleHealth)
	mux.HandleFunc("/execute-tool", h.handleExecuteTool)

	return mux
}
