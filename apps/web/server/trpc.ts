import { initTRPC, TRPCError } from '@trpc/server';
import superjson from 'superjson';
import { auth } from '../auth.js';

export const createTRPCContext = async (opts: { headers: Headers }) => {
  const session = await auth();
  return {
    session,
    ...opts,
  };
};

const t = initTRPC.context<typeof createTRPCContext>().create({
  transformer: superjson,
});

export const createTRPCRouter = t.router;
export const publicProcedure = t.procedure;

const enforceUserIsAuthed = t.middleware(({ ctx, next }) => {
  if (!ctx.session?.user) {
    throw new TRPCError({ code: 'UNAUTHORIZED' });
  }
  return next({
    ctx: {
      session: { ...ctx.session, user: ctx.session.user },
    },
  });
});

export const protectedProcedure = t.procedure.use(enforceUserIsAuthed);
