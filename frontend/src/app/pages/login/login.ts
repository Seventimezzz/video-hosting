import { Component, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { AuthService } from '../../core/auth.service';
import { errorMessage } from '../../core/errors';

@Component({
  selector: 'app-login',
  imports: [FormsModule],
  template: `
    <div class="card">
      <h2>{{ mode() === 'login' ? 'Вход' : 'Регистрация' }}</h2>
      <form class="form" (ngSubmit)="submit()">
        <label>
          Email
          <input type="email" name="email" [(ngModel)]="email" required autocomplete="email" />
        </label>
        <label>
          Пароль
          <input
            type="password"
            name="password"
            [(ngModel)]="password"
            required
            [autocomplete]="mode() === 'login' ? 'current-password' : 'new-password'"
          />
        </label>
        @if (error()) {
          <div class="error">{{ error() }}</div>
        }
        <div>
          <button class="primary" type="submit" [disabled]="busy()">
            {{ mode() === 'login' ? 'Войти' : 'Зарегистрироваться' }}
          </button>
        </div>
        <div class="muted">
          @if (mode() === 'login') {
            Нет аккаунта? <a href="" (click)="switchMode($event, 'register')">Регистрация</a>
          } @else {
            Уже есть аккаунт? <a href="" (click)="switchMode($event, 'login')">Вход</a>
          }
        </div>
      </form>
    </div>
  `,
})
export class Login {
  /** Куда вернуться после входа — ставит authGuard через ?next=. */
  readonly next = input<string>();

  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  protected email = '';
  protected password = '';
  protected readonly mode = signal<'login' | 'register'>('login');
  protected readonly busy = signal(false);
  protected readonly error = signal<string | null>(null);

  protected switchMode(event: Event, mode: 'login' | 'register'): void {
    event.preventDefault();
    this.mode.set(mode);
    this.error.set(null);
  }

  protected async submit(): Promise<void> {
    this.busy.set(true);
    this.error.set(null);
    try {
      if (this.mode() === 'register') {
        await this.auth.register(this.email, this.password);
      }
      await this.auth.login(this.email, this.password);
      await this.router.navigateByUrl(this.next() ?? '/videos');
    } catch (err) {
      this.error.set(errorMessage(err));
    } finally {
      this.busy.set(false);
    }
  }
}
