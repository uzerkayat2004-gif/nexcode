import { createTRPCRouter, publicProcedure, protectedProcedure } from '../trpc.js';
import { z } from 'zod';

export const appRouter = createTRPCRouter({
  healthcheck: publicProcedure.query(() => {
    return { status: 'ok', timestamp: new Date().toISOString() };
  }),

  user: createTRPCRouter({
    me: protectedProcedure.query(({ ctx }) => {
      return ctx.session.user;
    }),
  }),

  conversations: createTRPCRouter({
    list: protectedProcedure.query(() => {
      // TODO: Fetch from database
      return [];
    }),

    create: protectedProcedure
      .input(
        z.object({
          title: z.string().min(1),
          provider: z.string(),
          model: z.string(),
        })
      )
      .mutation(({ input }) => {
        // TODO: Create conversation in database
        return {
          id: crypto.randomUUID(),
          ...input,
          createdAt: new Date(),
        };
      }),
  }),

  apiKeys: createTRPCRouter({
    list: protectedProcedure.query(() => {
      // TODO: Fetch from database
      return [];
    }),

    create: protectedProcedure
      .input(
        z.object({
          name: z.string().min(1).max(100),
          expiresIn: z.number().optional(),
        })
      )
      .mutation(({ input }) => {
        const apiKey = `nxc_sk_${Array.from({ length: 32 }, () =>
          'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'.charAt(
            Math.floor(Math.random() * 62)
          )
        ).join('')}`;

        return {
          id: crypto.randomUUID(),
          name: input.name,
          key: apiKey,
          createdAt: new Date(),
        };
      }),

    revoke: protectedProcedure
      .input(z.object({ id: z.string().uuid() }))
      .mutation(({ input }) => {
        // TODO: Revoke API key in database
        return { success: true, id: input.id };
      }),
  }),
});

export type AppRouter = typeof appRouter;
