import { NextRequest, NextResponse } from 'next/server';

const deviceTokens = new Map<string, {
  token: string;
  userId: string | null;
  expiresAt: Date;
  verified: boolean;
}>();

export async function GET(request: NextRequest) {
  const token = request.nextUrl.searchParams.get('token');

  if (!token) {
    return NextResponse.json(
      { error: 'Token is required' },
      { status: 400 }
    );
  }

  const deviceToken = deviceTokens.get(token);

  if (!deviceToken) {
    return NextResponse.json(
      { error: 'Invalid token' },
      { status: 404 }
    );
  }

  if (new Date() > deviceToken.expiresAt) {
    deviceTokens.delete(token);
    return NextResponse.json(
      { error: 'Token expired', status: 'expired' },
      { status: 401 }
    );
  }

  if (!deviceToken.verified) {
    return NextResponse.json({
      status: 'pending',
      message: 'Waiting for user authorization',
    });
  }

  // Generate session JWT
  const sessionToken = crypto.randomUUID();

  return NextResponse.json({
    status: 'authorized',
    sessionToken,
    userId: deviceToken.userId,
    email: 'user@example.com', // TODO: Get from user record
  });
}
