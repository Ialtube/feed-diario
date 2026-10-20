-- El Rincón del Feeder: comentarios y noticias propuestas por los lectores.
-- Pégalo entero en Supabase → SQL Editor → New query → Run. Se puede ejecutar más de una vez.

-- ---------------------------------------------------------------- comentarios
create table if not exists public.comentarios (
  id bigint generated always as identity primary key,
  edicion date not null,
  nombre text not null check (char_length(nombre) between 1 and 40),
  texto text not null check (char_length(texto) between 1 and 1000),
  created_at timestamptz not null default now()
);
alter table public.comentarios enable row level security;
drop policy if exists "leer comentarios" on public.comentarios;
create policy "leer comentarios" on public.comentarios for select to anon using (true);
drop policy if exists "escribir comentarios" on public.comentarios;
create policy "escribir comentarios" on public.comentarios for insert to anon with check (true);

-- ---------------------------------------------------------------- noticias propuestas
create table if not exists public.propuestas (
  id bigint generated always as identity primary key,
  nombre text not null check (char_length(nombre) between 1 and 40),
  titulo text not null check (char_length(titulo) between 3 and 140),
  texto text not null check (char_length(texto) between 10 and 2000),
  imagen text check (imagen is null or char_length(imagen) <= 300),
  created_at timestamptz not null default now()
);
alter table public.propuestas enable row level security;
drop policy if exists "leer propuestas" on public.propuestas;
create policy "leer propuestas" on public.propuestas for select to anon using (true);
drop policy if exists "enviar propuestas" on public.propuestas;
create policy "enviar propuestas" on public.propuestas for insert to anon with check (true);

-- ---------------------------------------------------------------- imágenes de las propuestas
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('propuestas', 'propuestas', true, 5242880,
        array['image/jpeg', 'image/png', 'image/gif', 'image/webp'])
on conflict (id) do update set public = true, file_size_limit = 5242880,
  allowed_mime_types = array['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
drop policy if exists "subir imagenes de propuestas" on storage.objects;
create policy "subir imagenes de propuestas" on storage.objects
  for insert to anon with check (bucket_id = 'propuestas');

-- ---------------------------------------------------------------- sorteo de la grieta
-- Cada boleto: un nombre y tres números del 0 al 99. La fecha la pone siempre el servidor.
create table if not exists public.boletos (
  id bigint generated always as identity primary key,
  nombre text not null check (char_length(nombre) between 1 and 40),
  numeros smallint[] not null check (array_length(numeros, 1) = 3 and 0 <= all(numeros) and 99 >= all(numeros)),
  created_at timestamptz not null default now()
);
alter table public.boletos enable row level security;
drop policy if exists "leer boletos" on public.boletos;
create policy "leer boletos" on public.boletos for select to anon using (true);
drop policy if exists "comprar boletos" on public.boletos;
-- nadie puede colar un boleto con fecha antigua para un sorteo ya celebrado
create policy "comprar boletos" on public.boletos for insert to anon
  with check (created_at between now() - interval '2 minutes' and now() + interval '2 minutes');

-- ---------------------------------------------------------------- comentarios en cada noticia
-- pieza vacía = comentario a la edición entera («Cartas al director»)
alter table public.comentarios add column if not exists pieza integer;

-- ---------------------------------------------------------------- reacciones a las noticias
-- Cada navegador puede poner cada emoji una vez por noticia (no se pueden quitar).
create table if not exists public.reacciones (
  id bigint generated always as identity primary key,
  edicion date not null,
  pieza integer not null,
  emoji text not null check (emoji in ('😂', '💀', '🔥', '🤡', '🧂', '👑')),
  lector text not null check (char_length(lector) between 8 and 60),
  nombre text check (nombre is null or char_length(nombre) <= 40),
  created_at timestamptz not null default now(),
  unique (edicion, pieza, emoji, lector)
);
alter table public.reacciones enable row level security;
drop policy if exists "leer reacciones" on public.reacciones;
create policy "leer reacciones" on public.reacciones for select to anon using (true);
drop policy if exists "reaccionar" on public.reacciones;
create policy "reaccionar" on public.reacciones for insert to anon
  with check (created_at between now() - interval '2 minutes' and now() + interval '2 minutes');

-- ---------------------------------------------------------------- visitas
-- Quién abre cada página (con el nombre que eligió el lector, o anónimo). Una por día y página.
create table if not exists public.visitas (
  id bigint generated always as identity primary key,
  pagina text not null check (char_length(pagina) between 1 and 80),
  nombre text check (nombre is null or char_length(nombre) <= 40),
  lector text check (lector is null or char_length(lector) <= 60),
  created_at timestamptz not null default now()
);
alter table public.visitas enable row level security;
drop policy if exists "leer visitas" on public.visitas;
create policy "leer visitas" on public.visitas for select to anon using (true);
drop policy if exists "visitar" on public.visitas;
create policy "visitar" on public.visitas for insert to anon
  with check (created_at between now() - interval '2 minutes' and now() + interval '2 minutes');

-- ---------------------------------------------------------------- derecho de réplica
-- El aludido en una noticia contesta; la redacción la publica (con su respuesta) en la siguiente edición.
create table if not exists public.replicas (
  id bigint generated always as identity primary key,
  edicion date not null,
  pieza integer not null,
  nombre text not null check (char_length(nombre) between 1 and 40),
  texto text not null check (char_length(texto) between 10 and 800),
  created_at timestamptz not null default now()
);
alter table public.replicas enable row level security;
drop policy if exists "leer replicas" on public.replicas;
create policy "leer replicas" on public.replicas for select to anon using (true);
drop policy if exists "replicar" on public.replicas;
create policy "replicar" on public.replicas for insert to anon
  with check (created_at between now() - interval '2 minutes' and now() + interval '2 minutes');

-- ---------------------------------------------------------------- la porra
-- Cada lector apuesta (sin dinero) quién será el peor del grupo en la próxima edición.
create table if not exists public.porras (
  id bigint generated always as identity primary key,
  nombre text not null check (char_length(nombre) between 1 and 40),
  lector text check (lector is null or char_length(lector) <= 60),
  prediccion text not null check (char_length(prediccion) between 1 and 40),
  created_at timestamptz not null default now()
);
alter table public.porras enable row level security;
drop policy if exists "leer porras" on public.porras;
create policy "leer porras" on public.porras for select to anon using (true);
drop policy if exists "apostar" on public.porras;
create policy "apostar" on public.porras for insert to anon
  with check (created_at between now() - interval '2 minutes' and now() + interval '2 minutes');

-- ---------------------------------------------------------------- correcciones del administrador
-- El administrador edita las noticias en la web (modo edición) y cada cambio se guarda como
-- «antes / después». Todos pueden leerlas (la web las muestra al momento y la redacción aprende de
-- ellas), pero solo se pueden escribir a través de la función de abajo, con la clave de administrador.
-- En la base de datos solo se guarda la huella SHA-256 de la clave, nunca la clave.
create extension if not exists pgcrypto with schema extensions;
create table if not exists public.correcciones (
  id bigint generated always as identity primary key,
  edicion date not null,
  pieza integer not null,
  campo text not null check (char_length(campo) between 1 and 40),
  antes text not null check (char_length(antes) <= 6000),
  despues text not null check (char_length(despues) <= 6000),
  nota text check (nota is null or char_length(nota) <= 500),
  created_at timestamptz not null default now()
);
alter table public.correcciones enable row level security;
drop policy if exists "leer correcciones" on public.correcciones;
create policy "leer correcciones" on public.correcciones for select to anon using (true);

create or replace function public.es_admin(clave text) returns boolean
language sql security definer set search_path = public, extensions as $$
  select encode(extensions.digest(clave, 'sha256'), 'hex') = 'c29d3ebfa59f425dd4d9a2a20ed916587425674dcc96f441b9dd433ba5acd551'
$$;

create or replace function public.guardar_correccion(clave text, p_edicion date, p_pieza integer, p_campo text,
                                                     p_antes text, p_despues text, p_nota text default null)
returns bigint language plpgsql security definer set search_path = public, extensions as $$
declare nuevo bigint;
begin
  if not public.es_admin(clave) then
    raise exception 'Clave de administrador incorrecta' using errcode = '42501';
  end if;
  insert into public.correcciones (edicion, pieza, campo, antes, despues, nota)
  values (p_edicion, p_pieza, p_campo, p_antes, p_despues, nullif(trim(p_nota), ''))
  returning id into nuevo;
  return nuevo;
end $$;
revoke all on function public.guardar_correccion(text, date, integer, text, text, text, text) from public;
grant execute on function public.guardar_correccion(text, date, integer, text, text, text, text) to anon;
grant execute on function public.es_admin(text) to anon;

-- Hace que la API vea las tablas nuevas al momento
notify pgrst, 'reload schema';
