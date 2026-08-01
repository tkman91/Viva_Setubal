import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { formatApiError } from "@/lib/api";
import { UtensilsCrossed } from "lucide-react";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      <div
        className="hidden lg:block relative bg-primary"
        style={{
          backgroundImage:
            "url(https://images.pexels.com/photos/36092422/pexels-photo-36092422.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940)",
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      >
        <div className="absolute inset-0 bg-primary/70" />
        <div className="absolute bottom-0 left-0 p-12">
          <div className="w-12 h-12 bg-accent flex items-center justify-center mb-6">
            <UtensilsCrossed className="w-6 h-6 text-accent-foreground" />
          </div>
          <h2 className="font-display text-5xl font-black text-primary-foreground tracking-tighter leading-none">
            GESTÃO<br />RESTAURANTE
          </h2>
          <p className="text-primary-foreground/80 mt-4 max-w-sm">
            Stock, picagem de ponto geolocalizada, staff e faturação num só sítio.
          </p>
        </div>
      </div>

      <div className="flex items-center justify-center p-8 bg-background">
        <form onSubmit={submit} className="w-full max-w-sm fade-up">
          <div className="lg:hidden w-12 h-12 bg-primary flex items-center justify-center mb-6">
            <UtensilsCrossed className="w-6 h-6 text-primary-foreground" />
          </div>
          <div className="label-tech mb-2">Área reservada</div>
          <h1 className="font-display text-4xl font-bold tracking-tighter mb-8">Iniciar sessão</h1>

          {error && (
            <div data-testid="login-error" className="mb-4 p-3 bg-destructive/10 border border-destructive text-destructive text-sm">
              {error}
            </div>
          )}

          <label className="label-tech block mb-1">Email</label>
          <input
            data-testid="input-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="w-full mb-4 px-3 py-2.5 bg-card border border-input focus:outline-none focus:ring-2 focus:ring-primary text-sm"
            placeholder="o.teu.email@exemplo.pt"
          />
          <label className="label-tech block mb-1">Palavra-passe</label>
          <input
            data-testid="input-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="w-full mb-6 px-3 py-2.5 bg-card border border-input focus:outline-none focus:ring-2 focus:ring-primary text-sm"
            placeholder="••••••••"
          />
          <button
            data-testid="btn-login"
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-primary text-primary-foreground font-semibold text-sm hover:translate-y-[-1px] active:scale-[0.98] transition-transform duration-150 disabled:opacity-60"
          >
            {loading ? "A entrar..." : "Entrar"}
          </button>
        </form>
      </div>
    </div>
  );
}
