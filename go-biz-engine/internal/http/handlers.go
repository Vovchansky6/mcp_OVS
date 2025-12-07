package http

import (
	"encoding/json"
	"log"
	"net/http"

	"go-biz-engine/internal/tools"
)

// простой ответ health-check
type healthResponse struct {
	Status  string `json:"status"`
	Service string `json:"service"`
	Env     string `json:"env"`
	Version string `json:"version"`
}

func (h *Handler) handleHealth(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		w.Header().Set("Allow", http.MethodGet)
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	resp := healthResponse{
		Status:  "ok",
		Service: "go-biz-engine",
		Env:     h.cfg.Env,
		Version: h.cfg.Version,
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(resp)
}

func (h *Handler) handleExecuteTool(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.Header().Set("Allow", http.MethodPost)
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	defer r.Body.Close()

	var req tools.ExecuteRequest

	dec := json.NewDecoder(r.Body)
	dec.DisallowUnknownFields()

	if err := dec.Decode(&req); err != nil {
		http.Error(w, "invalid JSON: "+err.Error(), http.StatusBadRequest)
		return
	}

	// базовая валидация
	if req.ToolName == "" {
		http.Error(w, "tool_name is required", http.StatusBadRequest)
		return
	}
	if req.Params == nil {
		req.Params = make(map[string]interface{})
	}

	resp, err := tools.ExecuteTool(r.Context(), req, h.cfg.Version)
	if err != nil {
		log.Printf("ExecuteTool error: %v", err)

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusInternalServerError)

		_ = json.NewEncoder(w).Encode(map[string]interface{}{
			"status": "error",
			"error": map[string]interface{}{
				"code":    "INTERNAL_ERROR",
				"message": "internal server error",
			},
		})
		return
	}

	w.Header().Set("Content-Type", "application/json")
	// здесь по контракту обычно 200 OK, даже если resp.Status == "error"
	_ = json.NewEncoder(w).Encode(resp)
}
