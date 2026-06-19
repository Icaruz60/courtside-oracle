import { createClient } from "@supabase/supabase-js";
import type { Prediction, RunningRecord, ShapValue } from "./types";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

export const supabase = createClient(supabaseUrl, supabaseKey);

export async function getRecentPredictions(limit = 30): Promise<Prediction[]> {
  const { data, error } = await supabase
    .from("predictions")
    .select("*")
    .order("game_date", { ascending: false })
    .limit(limit);

  if (error) throw error;
  return data ?? [];
}

export async function getTodaysPredictions(): Promise<Prediction[]> {
  const today = new Date().toISOString().split("T")[0];
  const { data, error } = await supabase
    .from("predictions")
    .select("*")
    .eq("game_date", today)
    .order("created_at", { ascending: true });

  if (error) throw error;
  return data ?? [];
}

export async function getShapValues(predictionId: string): Promise<ShapValue[]> {
  const { data, error } = await supabase
    .from("shap_values")
    .select("*")
    .eq("prediction_id", predictionId)
    .order("shap_value", { ascending: false });

  if (error) throw error;
  return data ?? [];
}

export async function getRunningRecord(): Promise<RunningRecord | null> {
  const { data, error } = await supabase
    .from("running_record")
    .select("*")
    .eq("id", 1)
    .single();

  if (error) return null;
  return data;
}
