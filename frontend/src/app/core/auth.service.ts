import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { Observable, finalize, firstValueFrom, map, shareReplay } from 'rxjs';

import { User } from './models';

/**
 * Токены живут в httpOnly-cookie, которые ставит бэкенд, — JS их не видит и не хранит.
 * Браузер сам прикладывает cookie к запросам на /api, потому что фронт и API на одном
 * origin (через nginx). Здесь храним только «кто залогинен».
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);

  /** undefined — ещё не знаем, null — не залогинен. */
  readonly user = signal<User | null | undefined>(undefined);

  private refreshInFlight: Observable<void> | null = null;

  private loading: Promise<User | null> | null = null;

  /** Шапка и authGuard зовут это одновременно при старте — /api/me уходит один раз. */
  ensureLoaded(): Promise<User | null> {
    const current = this.user();
    if (current !== undefined) {
      return Promise.resolve(current);
    }
    this.loading ??= firstValueFrom(this.http.get<User>('/api/me'))
      .catch(() => null)
      .then((user) => {
        this.user.set(user);
        this.loading = null;
        return user;
      });
    return this.loading;
  }

  async login(email: string, password: string): Promise<void> {
    await firstValueFrom(this.http.post('/api/login', { email, password }));
    this.user.set(await firstValueFrom(this.http.get<User>('/api/me')));
  }

  async register(email: string, password: string): Promise<void> {
    await firstValueFrom(this.http.post('/api/register', { email, password }));
  }

  async logout(): Promise<void> {
    try {
      await firstValueFrom(this.http.post('/api/logout', {}));
    } finally {
      this.user.set(null);
    }
  }

  /**
   * Один общий refresh на все параллельные 401: иначе несколько запросов одновременно
   * пошлют один и тот же refresh-токен, первый его ротирует, остальные получат 401
   * (бэкенд считает повторное использование старого токена невалидным).
   */
  refresh(): Observable<void> {
    this.refreshInFlight ??= this.http.post('/api/refresh', {}).pipe(
      map(() => undefined),
      finalize(() => (this.refreshInFlight = null)),
      shareReplay(1),
    );
    return this.refreshInFlight;
  }

  markLoggedOut(): void {
    this.user.set(null);
  }
}
