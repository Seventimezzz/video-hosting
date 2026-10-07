import { Component, inject } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { AuthService } from './core/auth.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <header>
      <nav>
        <a routerLink="/videos" routerLinkActive="active">Видео</a>
        @if (auth.user()) {
          <a routerLink="/upload" routerLinkActive="active">Загрузить</a>
        }
      </nav>
      <div class="user">
        @if (auth.user(); as user) {
          <span class="muted">{{ user.email }}</span>
          <button (click)="logout()">Выйти</button>
        } @else if (auth.user() === null) {
          <a routerLink="/login">Войти</a>
        }
      </div>
    </header>
    <main>
      <router-outlet />
    </main>
  `,
  styles: `
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      padding: 12px 16px;
      background: var(--surface);
      border-bottom: 1px solid var(--border);
    }
    nav,
    .user {
      display: flex;
      align-items: center;
      gap: 16px;
    }
    nav a {
      text-decoration: none;
      color: var(--muted);
    }
    nav a.active {
      color: var(--text);
      font-weight: 600;
    }
  `,
})
export class App {
  protected readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  constructor() {
    // Узнаём при старте, есть ли живая сессия (cookie httpOnly, из JS их не видно).
    this.auth.ensureLoaded();
  }

  protected async logout(): Promise<void> {
    await this.auth.logout();
    await this.router.navigateByUrl('/videos');
  }
}
