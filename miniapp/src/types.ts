export type {
  AuthStatus,
  Daily,
  Overview,
  Plan,
  Profile,
  Rating,
  ReviewAttempt,
  ReviewItem,
  StudyLog,
  Subject,
  TimerState,
  Totals,
  Workspace,
} from "../../src/types";

export interface MiniSession {
  access_token: string;
  token_type: "Bearer";
  expires_at: string;
  account: { id: string; username: string };
  wechat_bound: boolean;
}

export interface AuthConfig {
  can_register: boolean;
  first_account: boolean;
  requires_bootstrap: boolean;
  registration_open: boolean;
  wechat_enabled: boolean;
}

export type WechatResult =
  | (MiniSession & { needs_binding: false })
  | {
      needs_binding: true;
      binding_token: string;
      expires_at: string;
    };
