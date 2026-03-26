import { NextRequest, NextResponse } from 'next/server';

const deviceTokens = new Map<string, {
  token: string;
  userId: string | null;
  expiresAt: Date;
  verified: boolean;
}>();

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { deviceCode } = body;

    if (!deviceCode) {
      return NextResponse.json(
        { error: 'Device code is required' },
        { status: 400 }
      );
    }

    const token = crypto.randomUUID();
    const expiresAt = new Date(Date.now() + 15 * 60 * 1000); // 15 minutes

    deviceTokens.set(token, {
      token,
      userId: null,
      expiresAt,
      verified: false,
    });

    return NextResponse.json({
      deviceCode,
      token,
      expiresAt: expiresAt.toISOString(),
    });
  } catch {
    return NextResponse.json(
      { error: 'Invalid request' },
      { status: 400 }
    );
  }
}
