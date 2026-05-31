import * as Sentry from '@sentry/nextjs';

import { getSentryInitOptions } from './src/lib/sentry';

Sentry.init(getSentryInitOptions());
