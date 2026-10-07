import { HttpErrorResponse } from '@angular/common/http';

/** Достаёт текст ошибки из ответа FastAPI ({"detail": "..."}) или из сетевой ошибки. */
export function errorMessage(err: unknown): string {
  if (err instanceof HttpErrorResponse) {
    if (err.status === 0) {
      return 'Сервер недоступен';
    }
    if (err.ok) {
      // 2xx, но тело не JSON: /api ответил не FastAPI, а dev-сервер своим index.html.
      return 'API вернул не JSON. Приложение нужно открывать через nginx: http://localhost:8080';
    }
    const detail: unknown = err.error?.detail;
    if (typeof detail === 'string') {
      return detail;
    }
    if (Array.isArray(detail) && detail[0]?.msg) {
      return detail[0].msg; // ошибка валидации pydantic (422)
    }
    if (err.status === 413) {
      return 'Слишком большой запрос (проверь client_max_body_size в nginx)';
    }
    return `Ошибка ${err.status}`;
  }
  return err instanceof Error ? err.message : String(err);
}
