using System.Text;
using ParserModule.Nodes;
using ParserModule.Nodes.Expressions;
using ParserModule.Visitors;

namespace ParserModule;

public sealed class AstPrinter : IAstNodeVisitor
{
    private readonly StringBuilder _sb = new();
    
    public void VisitLiteralInteger(LiteralIntegerExpressionNode integerNumberExpression)
    {
        _sb.Append(integerNumberExpression.Token.Lexeme);
    }

    public void VisitLiteralBool(LiteralBoolExpressionNode literalBoolExpressionNode)
    {
        _sb.Append(literalBoolExpressionNode.Token.Lexeme);       
    }

    public void VisitBinary(BinaryExpressionNode binaryExpressionNode)
    {
        _sb.Append('(');
        binaryExpressionNode.Left.Accept(this);
        _sb.Append(binaryExpressionNode.Op.Lexeme);
        binaryExpressionNode.Right.Accept(this);       
        _sb.Append(')');       
    }

    public void VisitUnary(UnaryExpressionNode unaryExpressionNode)
    {
        if (unaryExpressionNode.IsPrefix)
            _sb.Append(unaryExpressionNode.Operator.Lexeme);
        
        unaryExpressionNode.Value.Accept(this);       
        if (!unaryExpressionNode.IsPrefix)
            _sb.Append(unaryExpressionNode.Operator.Lexeme);       
    }

    public void VisitIdentifier(IdentifierExpressionNode node)
    {
        _sb.Append(node.Token.Lexeme);
    }

    public void VisitVarDefinition(VarDefinitionStatementNode node)
    {
        _sb.Append("var ");       
        _sb.Append(node.Name);
        if (node.Type != null)
        {
            _sb.Append(':');
            _sb.Append(' ');
            node.Type.Accept(this);
        }
        _sb.Append(' ');
        _sb.Append('=');
        _sb.Append(' ');
        node.Value.Accept(this);
        _sb.Append(';');       
    }

    public void VisitForStatement(ForStatemetNode node)
    {
        _sb.Append("for (");
        node.Initializer.Accept(this);
        
        node.Condition.Accept(this);
        _sb.Append(';');
        
        node.Incrementor.Accept(this);
        _sb.Append(')');
        
        node.Body.Accept(this);       
    }

    public void VisitVarDeclaration(VarDeclarationStatementNode node)
    {
        _sb.Append("var ");
        _sb.Append(node.Name);
        if (node.Type != null)
        {
            _sb.Append(':');
            _sb.Append(' ');
            node.Type.Accept(this);
        }
        _sb.Append(';');       
    }

    public void VisitVarAssignment(VarAssignmentStatementNode node)
    {
        _sb.Append(node.Name);
        _sb.Append(' ');
        _sb.Append('=');
        _sb.Append(' ');
        node.Value.Accept(this);
        _sb.Append(';');       
    }

    public void VisitWhileStatement(WhileStatementNode node)
    {
        _sb.Append("while ( ");
        node.Condition.Accept(this);
        _sb.Append(" ) ");
        node.Body.Accept(this);
    }

    public void VisitNamedType(NamedTypeNode node)
    {
        _sb.Append(node.Identifier);
    }

    public void VisitPtrType(PtrTypeNode node)
    {
        _sb.Append("ptr");
        if (node.GenericType != null)
        {
            _sb.Append('<');
            node.GenericType.Accept(this);
            _sb.Append('>');       
        }
    }

    public void VisitBlockStatement(BlockStatementNode node)
    {
        _sb.Append('{');
        _sb.Append('\n');
        foreach (var statement in node.Statements)
        {
            _sb.Append('\t');
            statement.Accept(this);
            _sb.Append('\n');
        }
        _sb.Append('}');
    }

    public void VisitFunctionDefinition(FunctionDefinitionNode node)
    {
        VisitFunctionSignature(node.Signature);
        node.Body.Accept(this);
    }

    public void VisitReturnStatementNode(ReturnStatementNode node)
    {
        _sb.Append("return");
        if (node.Result != null)
        {
            _sb.Append(' ');
            node.Result.Accept(this);
        }
        _sb.Append(';');       
    }

    public void VisitParameterNode(FunctionParameter functionParameter)
    {
        _sb.Append(functionParameter.Name);
        _sb.Append(':');
        functionParameter.Type.Accept(this);
    }

    public void VisitStructImport(ImportStatementNode node)
    {
        _sb.Append("import ");
        node.QualifiedIdentifier.Accept(this);
        _sb.Append(" as ");
        _sb.Append(node.AliasName);
        _sb.Append(';');
    }

    public void VisitQualifiedIdentifier(QualifiedIdentifierExpressionNode node)
    {
        for (var i = 0; i < node.Parts.Count - 1; i++)
        {
            _sb.Append(node.Parts[i]);
            _sb.Append('.');
        }
        _sb.Append(node.Parts[^1]);
    }

    public void VisitStructDefinition(StructDefinitionNode node)
    {
        _sb.Append("struct ");
        _sb.Append(node.Name);
        _sb.Append('{');
        _sb.AppendLine();
        foreach (var prop in node.Properties)
        {
            _sb.Append('\t');
            _sb.Append(prop.Name);
            _sb.Append(':');
            _sb.Append(' ');
            prop.Type.Accept(this);
            _sb.AppendLine();       
        }
        _sb.Append('}');
    }

    public void VisitExternFunctionDeclaration(ExternFunctionDeclarationNode node)
    {
        _sb.Append("extern ");
        VisitFunctionSignature(node.Signature);
    }

    public void VisitFunctionSignature(FunctionSignature node)
    {
        _sb.Append("func ");
        _sb.Append(node.Name);
        _sb.Append('(');
        if (node.Parameters.Count > 0)
        {
            for (var i = 0; i < node.Parameters.Count - 1; i++)
            {
                VisitParameterNode(node.Parameters[i]);
                _sb.Append(',');
                _sb.Append(' ');
            }
            VisitParameterNode(node.Parameters[^1]);
        }
        _sb.Append(')');
        if (node.ReturnType != null)
        {
            _sb.Append(" -> ");
            node.ReturnType.Accept(this);       
        }
        _sb.Append(' ');
    }

    public void VisitModuleDefinition(ModuleDefinitionNode node)
    {
        _sb.Append("module ");
        node.Name.Accept(this);
        _sb.Append(" {").AppendLine();
        _sb.Append("\t#metadata ");
        _sb.AppendLine(node.Metadata.ToJsonString());
        foreach (var statement in node.Body)
        {
            statement.Accept(this);
        }
        _sb.Append("}");       
    }

    public void VisitProgram(CompilationUnit node)
    {
        throw new NotImplementedException();
    }

    public override string ToString()
    {
        return _sb.ToString();       
    }

    public void VisitIfStatementNode(IfStatementNode node)
    {
        _sb.Append("if ");
        node.Condition.Accept(this);
        _sb.Append(' ');
        node.ThenBranch.Accept(this);
        if (node.ElseBranch != null)
        {
            _sb.Append(" else ");
            node.ElseBranch.Accept(this);
        }
    }
}