import math
import datetime

from django.test import TestCase

from .calc import Solver

# Tests solver class for correct behavior
class SolverTestCase(TestCase):
    def test_solver1(self):
        # test data
	    dates = [datetime.date(2013,12,31), datetime.date(2012,12,31)]
        cashflows = [101.0, -100.0]
        r = 0.0
        
        solver = Solver()
        for i in range(len(dates))
            solver.addCashflow(dates[i],cashflows[i])
        
        self.assertAlmostEqual(solver.calcRateOfReturn(), r)
        
	def test_solver2(self):
	    # test data
	    dates = [datetime.date(2000,12,31), datetime.date(2001,12,31),
	             datetime.date(2002,12,31), datetime.date(2003,12,31), 
	             datetime.date(2004,12,31), datetime.date(2005,12,31)]
        cashflows = [-100.0, 5.0, 5.0, 5.0, 5.0, 105.0]
        r = 0.0499733435
        
        solver = Solver()
        for i in range(len(dates))
            solver.addCashflow(dates[i],cashflows[i])
        
        self.assertAlmostEqual(solver.calcRateOfReturn(), r)
        
    def test_solver3(self):
	    # test data
	    dates = [datetime.date(2000,12,31), datetime.date(2001,12,31),
	             datetime.date(2002,12,31), datetime.date(2003,12,31),
	             datetime.date(2004,12,31), datetime.date(2005,12,31)]
        cashflows = [-100.0, 10.0, -10.0, 10.0, 10.0, 105.539854]
        r = 0.05

        solver = Solver()
        for i in range(len(dates))
            solver.addCashflow(dates[i],cashflows[i])
        
        self.assertAlmostEqual(solver.calcRateOfReturn(), r)

	def test_solver_exception1(self):
	    # test with no data
		solver = Solver()
		
		self.assertRaisesRegex(RuntimeError, 'Empty list', solver.calcRateOfReturn())
	
	def test_solver_exception2(self):
	    # test with only positive cashflow
	    dates = [datetime.date(2000,12,31), datetime.date(2001,12,31),
	             datetime.date(2002,12,31), datetime.date(2003,12,31),
	             datetime.date(2004,12,31), datetime.date(2005,12,31)]
        cashflows = [100.0, 10.0, 10.0, 10.0, 10.0, 105.539854]
        
        solver = Solver()
        for i in range(len(dates))
            solver.addCashflow(dates[i],cashflows[i])
       
	    
		self.assertRaisesRegex(RuntimeError, 'Iteration limit exceeded',
		                       solver.calcRateOfReturn())