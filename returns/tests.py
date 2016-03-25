import math
import datetime

from django.test import TestCase

from .calc import newtonSolve, solverF, solverDF, callSolver

class SolverTests(TestCase):
    def test_basic_newtonSolve1(self):
        f = lambda x: x**3 - 1.0
        df = lambda x: 3*x**2

        self.assertAlmostEqual(newtonSolve(f, df, 0.0), 1.0)

    def test_basic_newtonSolve2(self):
        f = lambda x: math.exp(x) - 1.0
        df = lambda x: math.exp(x)

        self.assertAlmostEqual(newtonSolve(f, df, 1.0), 0.0)

    def test_solverF1(self):
        dates = [datetime.date(2013,12,31), datetime.date(2012,12,31)]
        cashflows = [101.0, -100.0]
        r = 0.01

        self.assertAlmostEqual(solverF(r, dates, cashflows), 0.0)

    def test_solverF2(self):
        dates = [datetime.date(2000,12,31), datetime.date(2001,12,31), datetime.date(2002,12,31), datetime.date(2003,12,31), datetime.date(2004,12,31), datetime.date(2005,12,31)]
        cashflows = [-100.0, 5.0, 5.0, 5.0, 5.0, 105.0]
        r = 0.0499733435

        self.assertAlmostEqual(solverF(r, dates, cashflows), 0.0)

    def test_solverDF1(self):
        dates = [datetime.date(2013,12,31), datetime.date(2012,12,31)]
        cashflows = [101.0, -100.0]
        r = 0.01

        self.assertAlmostEqual(solverDF(r, dates, cashflows), -100.0)

    def test_solverDF2(self):
        dates = [datetime.date(2000,12,31), datetime.date(2001,12,31), datetime.date(2002,12,31), datetime.date(2003,12,31), datetime.date(2004,12,31), datetime.date(2005,12,31)]
        cashflows = [-100.0, 5.0, 5.0, 5.0, 5.0, 105.0]
        r = 0.0499733435

        self.assertAlmostEqual(solverDF(r, dates, cashflows), -433.18244089)

    def test_callSolver1(self):
        dates = [datetime.date(2013,12,31), datetime.date(2012,12,31)]
        cashflows = [101.0, -100.0]

        self.assertAlmostEqual(callSolver(dates, cashflows), 0.01)  

    def test_callSolver2(self):
        dates = [datetime.date(2000,12,31), datetime.date(2001,12,31), datetime.date(2002,12,31), datetime.date(2003,12,31), datetime.date(2004,12,31), datetime.date(2005,12,31)]
        cashflows = [-100.0, 5.0, 5.0, 5.0, 5.0, 105.0]

        self.assertAlmostEqual(callSolver(dates, cashflows), 0.0499733435)


    def test_callSolver3(self):
        dates = [datetime.date(2000,12,31), datetime.date(2001,12,31), datetime.date(2002,12,31), datetime.date(2003,12,31), datetime.date(2004,12,31), datetime.date(2005,12,31)]
        cashflows = [-100.0, 10.0, -10.0, 10.0, 10.0, 105.539854]

        self.assertAlmostEqual(callSolver(dates, cashflows), 0.05)
 
        
