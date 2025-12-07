package tools

import (
	"context"
	"encoding/json"
	"time"
)

// ExecuteRequest соответствует JSON-запросу /execute-tool.
type ExecuteRequest struct {
	ToolName      string                 `json:"tool_name"`
	Params        map[string]interface{} `json:"params"`
	CorrelationID string                 `json:"correlation_id"`
	UserID        string                 `json:"user_id,omitempty"`
	RequestTS     string                 `json:"request_ts,omitempty"`
	Context       map[string]interface{} `json:"context,omitempty"`
}

// ExecuteResponse соответствует JSON-ответу.
type ExecuteResponse struct {
	Status        string                 `json:"status"`                   // "success" | "error"
	ToolName      string                 `json:"tool_name"`                // echo из запроса
	CorrelationID string                 `json:"correlation_id"`           // echo из запроса
	Data          map[string]interface{} `json:"data,omitempty"`           // произвольный payload
	Error         *ErrorInfo             `json:"error,omitempty"`          // бизнес-ошибка
	Metrics       Metrics                `json:"metrics,omitempty"`        // метрики выполнения
	EngineVersion string                 `json:"engine_version,omitempty"` // версия сервиса
}

// ErrorInfo описывает бизнес-ошибку.
type ErrorInfo struct {
	Code    string                 `json:"code"`
	Message string                 `json:"message"`
	Details map[string]interface{} `json:"details,omitempty"`
}

// Metrics — метрики выполнения.
type Metrics struct {
	LatencyMs     int64 `json:"latency_ms,omitempty"`
	EngineTimeMs  int64 `json:"engine_time_ms,omitempty"`
	UpstreamCalls int   `json:"upstream_calls,omitempty"`
}

// helper: мапа params → структура
func decodeParams(params map[string]interface{}, target interface{}) error {
	b, err := json.Marshal(params)
	if err != nil {
		return err
	}
	return json.Unmarshal(b, target)
}

// ExecuteTool — центральная точка маршрутизации бизнес-логики tools.
func ExecuteTool(ctx context.Context, req ExecuteRequest, engineVersion string) (ExecuteResponse, error) {
	start := time.Now()

	resp := ExecuteResponse{
		ToolName:      req.ToolName,
		CorrelationID: req.CorrelationID,
		EngineVersion: engineVersion,
	}

	switch req.ToolName {
	case "financial_analyzer":
		var fp FinancialParams
		if err := decodeParams(req.Params, &fp); err != nil {
			resp.Status = "error"
			resp.Error = &ErrorInfo{
				Code:    "INVALID_PARAMS",
				Message: "invalid parameters for financial_analyzer: " + err.Error(),
			}
			break
		}
		// дефолт на всякий случай
		if fp.Days <= 0 {
			fp.Days = 30
		}

		result, err := ExecuteFinancialAnalyzer(ctx, fp)
		if err != nil {
			// бизнес-ошибка: вернём её в JSON, но не как 500
			resp.Status = "error"
			resp.Error = &ErrorInfo{
				Code:    "FINANCIAL_ANALYZER_ERROR",
				Message: err.Error(),
			}
			break
		}

		resp.Status = "success"
		resp.Data = map[string]interface{}{
			"rate_avg":   result.RateAvg,
			"rate_min":   result.RateMin,
			"rate_max":   result.RateMax,
			"volatility": result.Volatility,
			"raw":        result.Raw,
		}

	default:
		resp.Status = "error"
		resp.Error = &ErrorInfo{
			Code:    "UNKNOWN_TOOL",
			Message: "tool not supported: " + req.ToolName,
		}
	}

	resp.Metrics.LatencyMs = time.Since(start).Milliseconds()
	resp.Metrics.EngineTimeMs = resp.Metrics.LatencyMs
	// resp.Metrics.UpstreamCalls можно заполнять отдельно внутри конкретных tools

	return resp, nil
}
